package setup

import (
	_ "embed"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"regexp"
	"runtime"
	"slices"
	"strconv"
	"strings"
	"time"
)

//go:embed assets/required-tools.json
var requiredTools []byte

func audit(args arguments) (object, error) {
	project, err := projectDirectory(args.value("project-root"), "--project-root must be an existing directory")
	if err != nil {
		return nil, err
	}
	jvm := args.has("jvm")
	if !jvm && (args.has("archunit") || args.has("junit") || args.has("jacoco-module") || args.has("jacoco")) {
		return nil, errors.New("JUnit, JaCoCo and ArchUnit observations require a JVM build")
	}
	if !jvm && args.has("build-root") {
		return nil, errors.New("--build-root requires a JVM build")
	}
	build, err := resolveBuild(project, args.value("build-root"))
	if err != nil {
		return nil, err
	}
	mise := checkMise(project)
	requirements := []object{mise}
	requirements = append(requirements, checkRequiredTools(project, miseReader(project, mise))...)
	if jvm && !slices.ContainsFunc(requirements, func(row object) bool { return row["status"] != "satisfied" }) {
		execute := miseReader(build, mise)
		requirements = append(requirements, checkJava(build, project, execute, args.value("jvm")), checkGradle(build, project, execute))
		junit, err := checkDependency("junit5", args["junit"])
		if err != nil {
			return nil, err
		}
		jacoco, err := checkJacoco(repeated(args, "jacoco-module"), args["jacoco"])
		if err != nil {
			return nil, err
		}
		archunit, err := checkDependency("archunit", args["archunit"])
		if err != nil {
			return nil, err
		}
		requirements = append(requirements, junit, jacoco, archunit)
	}
	for _, tool := range []string{"ktlint", "detekt"} {
		for _, observation := range args[tool] {
			scope, status, source := observation[0], observation[1], observation[2]
			if strings.TrimSpace(scope) == "" || !validStatus(status) || strings.TrimSpace(source) == "" {
				return nil, fmt.Errorf("Provide %s scope, satisfied/failed/unverified status and evidence", tool)
			}
			requirements = append(requirements, object{"id": tool, "scope": scope, "required": true,
				"title": "Project " + tool + " integration", "status": status, "evidence": object{"observation": source}})
		}
	}
	system, machine := platform()
	var buildRoot any
	if jvm {
		buildRoot = build
	}
	return object{"project_root": project, "build_root": buildRoot, "checked_at": time.Now().UTC().Format("2006-01-02T15:04:05.000000+00:00"),
		"system": system, "machine": machine, "requirements": requirements,
		"compliant": !slices.ContainsFunc(requirements, func(row object) bool { return row["status"] != "satisfied" })}, nil
}

func platform() (string, string) {
	system := runtime.GOOS
	system = strings.ToUpper(system[:1]) + system[1:]
	machine := runtime.GOARCH
	if runtime.GOOS == "windows" {
		if arch, ok := os.LookupEnv("PROCESSOR_ARCHITEW6432"); ok && arch != "" {
			return system, arch
		}
		if arch := os.Getenv("PROCESSOR_ARCHITECTURE"); arch != "" {
			return system, arch
		}
		return system, strings.ToUpper(machine)
	}
	switch machine {
	case "amd64":
		machine = "x86_64"
	case "arm64":
		if runtime.GOOS != "darwin" {
			machine = "aarch64"
		}
	case "386":
		machine = "i686"
	}
	return system, machine
}

func resolveBuild(project, value string) (string, error) {
	if value == "" {
		return project, nil
	}
	build, err := projectDirectory(anchored(project, value), "--build-root must be a JVM build directory inside the project")
	if err != nil {
		return "", err
	}
	if !inside(project, build) {
		return "", errors.New("--build-root must be a JVM build directory inside the project")
	}
	return build, nil
}

func jvmStep(args arguments) (object, error) {
	project, err := projectDirectory(args.value("project-root"), "--project-root must be an existing directory")
	if err != nil {
		return nil, err
	}
	build, err := resolveBuild(project, args.value("build-root"))
	if err != nil {
		return nil, err
	}
	switch step := args.value("step"); step {
	case "junit5", "archunit":
		return checkDependency(step, args["observation"])
	case "jacoco":
		return checkJacoco(repeated(args, "jacoco-module"), args["jacoco"])
	case "jdk":
		return checkJava(build, project, miseReader(build, checkMise(build)), args.value("jdk")), nil
	default:
		return checkGradle(build, project, miseReader(build, checkMise(build))), nil
	}
}

func checkRequiredTools(project string, execute miseExecute) []object {
	order := fieldOrder{}
	value, _ := decodeJSON(requiredTools, order)
	requests := asObject(value)
	requirements := []object{}
	for _, binary := range order[""] {
		request := asString(requests[binary])
		evidence := object{}
		row := object{"id": binary, "title": "Project " + binary + " installed through mise", "required": true,
			"tool_request": request, "use_command": []string{"mise", "use", "--path", project, request},
			"status": "unverified", "version": nil, "evidence": evidence}
		requirements = append(requirements, row)
		if execute == nil {
			evidence["error"] = "Verify mise on PATH first"
			continue
		}
		err := func() error {
			provider, err := execute([]string{"mise", "which", binary, "--plugin"})
			if err != nil {
				return err
			}
			provider = strings.TrimSpace(provider)
			evidence["provider"] = provider
			if err := checkBinary(execute, project, provider, binary); err != nil {
				return err
			}
			version, err := execute([]string{"mise", "which", binary, "--version"})
			if err != nil {
				return err
			}
			version = strings.TrimSpace(version)
			if version == "" {
				return fmt.Errorf("mise returned no active version for %s", binary)
			}
			row["version"] = version
			output, err := execute([]string{"mise", "exec", "--", binary, "--version"})
			if err != nil {
				return err
			}
			evidence["output"] = strings.TrimSpace(output)
			if evidence["output"] == "" {
				return fmt.Errorf("%s --version returned no output", binary)
			}
			return nil
		}()
		if err != nil {
			row["status"], evidence["error"] = "failed", commandMessage(err)
		} else {
			row["status"] = "satisfied"
		}
	}
	return requirements
}

var jdkVersion = regexp.MustCompile(`^(?:[A-Za-z][A-Za-z0-9-]*-)?\d+(?:u\d+)?(?:[._+-][A-Za-z0-9]+)*$`)
var vendorPrefix = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9-]*?-(\d)`)

func checkJava(build, project string, execute miseExecute, requested string) object {
	evidence := object{}
	row := object{"id": "java", "required": true, "title": "Project JDK installed through mise",
		"requested_version": optionalText(requested), "version": nil, "status": "failed", "evidence": evidence}
	if !jdkVersion.MatchString(requested) {
		evidence["error"] = "Identify the JDK version from project sources"
		return row
	}
	row["use_command"] = []string{"mise", "use", "--path", build, "java@" + requested}
	if execute == nil {
		evidence["error"] = "Verify mise on PATH first"
		return row
	}
	if err := checkBinary(execute, project, "java", "java", "javac"); err != nil {
		evidence["error"] = commandMessage(err)
		return row
	}
	for _, binary := range []string{"java", "javac"} {
		output, err := execute([]string{"mise", "which", binary, "--version"})
		if err != nil {
			evidence["error"] = commandMessage(err)
			return row
		}
		evidence[binary] = strings.TrimSpace(output)
	}
	version := asString(evidence["java"])
	row["version"] = version
	observed := version
	if requested[0] >= '0' && requested[0] <= '9' {
		observed = vendorPrefix.ReplaceAllString(observed, "$1")
	}
	match, _ := regexp.MatchString("^"+regexp.QuoteMeta(requested)+`(?:$|[._+-]|u\d)`, observed)
	if evidence["javac"] == version && match {
		row["status"] = "satisfied"
	} else {
		evidence["error"] = "The active Java runtime and compiler must match the project JDK"
	}
	return row
}

func validStatus(value string) bool {
	return value == "satisfied" || value == "failed" || value == "unverified"
}

func checkJacoco(modules []string, observations [][]string) (object, error) {
	expected := sortedUnique(modules)
	if len(expected) != len(modules) || slices.ContainsFunc(expected, func(module string) bool { return strings.TrimSpace(module) == "" }) {
		return nil, errors.New("Provide distinct nonempty --jacoco-module paths from the build")
	}
	observed := object{}
	failed, satisfied := false, true
	for _, observation := range observations {
		module, status, source := observation[0], observation[1], observation[2]
		if !slices.Contains(expected, module) || observed[module] != nil {
			return nil, fmt.Errorf("Unexpected or repeated JaCoCo module: %s", module)
		}
		if !validStatus(status) || strings.TrimSpace(source) == "" {
			return nil, fmt.Errorf("Provide a JaCoCo check status and evidence for %s", module)
		}
		observed[module] = object{"status": status, "source": source}
		failed = failed || status == "failed"
		satisfied = satisfied && status == "satisfied"
	}
	missing := []string{}
	for _, module := range expected {
		if observed[module] == nil {
			missing = append(missing, module)
		}
	}
	status := "unverified"
	if failed {
		status = "failed"
	} else if len(missing) == 0 && len(observed) > 0 && satisfied {
		status = "satisfied"
	}
	return object{"id": "jacoco", "required": true, "title": "JaCoCo coverage of all JVM modules",
		"status": status, "evidence": object{"observations": observed, "missing_modules": missing}}, nil
}

const archunitMetadata = "https://repo.maven.apache.org/maven2/com/tngtech/archunit/archunit/maven-metadata.xml"

var junitVersion = regexp.MustCompile(`^5\.\d+\.\d+(?:[-+][\w.-]+)?$`)
var archunitVersion = regexp.MustCompile(`^[0-9]+\.[0-9]+\.[0-9]+$`)

func checkDependency(step string, observations [][]string) (object, error) {
	id, name, title := "junit", "JUnit", "JVM tests use JUnit Jupiter 5"
	if step == "archunit" {
		id, name, title = "archunit", "ArchUnit", "Latest stable ArchUnit test dependency"
	}
	dependencies := []object{}
	for _, observation := range observations {
		version, source := observation[0], observation[1]
		if strings.TrimSpace(version) == "" || strings.TrimSpace(source) == "" {
			return nil, fmt.Errorf("Provide the observed %s version or 'missing', and its evidence", name)
		}
		dependencies = append(dependencies, object{"version": version, "source": source})
	}
	evidence := object{"dependencies": dependencies}
	result := object{"id": id, "required": true, "title": title, "status": "unverified", "evidence": evidence}
	matches := junitVersion.MatchString
	if step == "archunit" {
		evidence["release_source"], result["latest_stable"] = archunitMetadata, nil
		latest, err := latestArchunit()
		if err != nil {
			evidence["release_error"] = err.Error()
			if slices.ContainsFunc(dependencies, func(row object) bool { return row["version"] == "missing" }) {
				result["status"] = "failed"
			}
			return result, nil
		}
		result["latest_stable"] = latest
		matches = func(version string) bool { return version == latest }
	}
	if len(dependencies) > 0 {
		result["status"] = "satisfied"
	}
	for _, dependency := range dependencies {
		version := asString(dependency["version"])
		if version == "unverified" {
			result["status"] = "unverified"
		} else if !matches(version) {
			result["status"] = "failed"
			break
		}
	}
	return result, nil
}

func releaseMetadata(url string) ([]byte, error) {
	client := http.Client{Timeout: 5 * time.Second}
	response, err := client.Get(url)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	if response.StatusCode >= 400 {
		status := strings.TrimPrefix(response.Status, strconv.Itoa(response.StatusCode)+" ")
		return nil, fmt.Errorf("HTTP Error %d: %s", response.StatusCode, status)
	}
	return io.ReadAll(io.LimitReader(response.Body, 4<<20))
}

func latestArchunit() (string, error) {
	raw, err := releaseMetadata(archunitMetadata)
	if err != nil {
		return "", err
	}
	var metadata struct {
		Group    string   `xml:"groupId"`
		Artifact string   `xml:"artifactId"`
		Versions []string `xml:"versioning>versions>version"`
	}
	if err := xml.Unmarshal(raw, &metadata); err != nil {
		return "", err
	}
	if metadata.Group != "com.tngtech.archunit" || metadata.Artifact != "archunit" {
		return "", errors.New("Unexpected ArchUnit Maven metadata")
	}
	latest := ""
	for _, version := range metadata.Versions {
		if archunitVersion.MatchString(version) && (latest == "" || compareVersions(version, latest) > 0) {
			latest = version
		}
	}
	if latest == "" {
		return "", errors.New("No stable ArchUnit version found in Maven Central")
	}
	return latest, nil
}

func compareVersions(left, right string) int {
	parts := func(version string) []int {
		values := []int{}
		for _, text := range strings.Split(version, ".") {
			value, _ := strconv.Atoi(text)
			values = append(values, value)
		}
		for len(values) > 1 && values[len(values)-1] == 0 {
			values = values[:len(values)-1]
		}
		return values
	}
	return slices.Compare(parts(left), parts(right))
}
