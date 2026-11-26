package setup

import (
	"errors"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
)

const gradleRelease = "https://services.gradle.org/versions/current"

var (
	distributionURL = regexp.MustCompile(`(?m)^[ \t]*distributionUrl(?:[ \t]*[=:][ \t]*|[ \t]+)([^\r\n]*)`)
	gradleArchive   = regexp.MustCompile(`^gradle-(\d+(?:\.\d+)+(?:-[\w.-]+)?)-(?:bin|all)\.zip$`)
	gradleVersion   = regexp.MustCompile(`^(\d+(?:\.\d+)+)(?:-([\w.-]+))?$`)
	stableGradle    = regexp.MustCompile(`^\d+(?:\.\d+)+$`)
	previewGradle   = regexp.MustCompile(`(?i)^(?:rc-\d+|milestone-\d+|\d{8,}.*|snapshot)$`)
)

func gradleWrapper(project string) object {
	launcher := "gradlew"
	if runtime.GOOS == "windows" {
		launcher += ".bat"
	}
	properties := filepath.Join("gradle", "wrapper", "gradle-wrapper.properties")
	files := []string{launcher, filepath.Join("gradle", "wrapper", "gradle-wrapper.jar"), properties}
	missing := []string{}
	for _, file := range files {
		info, err := os.Stat(filepath.Join(project, file))
		if err != nil || !info.Mode().IsRegular() || info.Size() == 0 {
			missing = append(missing, file)
		}
	}
	if len(missing) > 0 {
		status := "incomplete"
		if len(missing) == len(files) {
			status = "not_found"
		}
		return object{"status": status, "missing": missing}
	}
	info, err := os.Stat(filepath.Join(project, launcher))
	if err != nil {
		return object{"status": "failed", "error": err.Error()}
	}
	if runtime.GOOS != "windows" && info.Mode().Perm()&0o111 == 0 {
		return object{"status": "incomplete", "error": "gradlew is not executable"}
	}
	raw, err := os.ReadFile(filepath.Join(project, properties))
	if err != nil {
		return object{"status": "failed", "error": err.Error()}
	}
	urls := distributionURL.FindAllSubmatch(raw, -1)
	if len(urls) == 0 || strings.TrimSpace(string(urls[len(urls)-1][1])) == "" {
		return object{"status": "incomplete", "error": "Missing distributionUrl"}
	}
	value := strings.TrimSpace(string(urls[len(urls)-1][1]))
	if end := strings.IndexAny(value, "?#"); end >= 0 {
		value = value[:end]
	}
	archive := value[strings.LastIndexByte(value, '/')+1:]
	var version any
	if match := gradleArchive.FindStringSubmatch(archive); match != nil {
		version = match[1]
	}
	return object{"status": "configured", "version": version, "launcher": launcher}
}

func checkGradle(build, project string, execute miseExecute) object {
	wrapper, mise := gradleWrapper(build), object{"status": "unverified"}
	if execute != nil {
		err := func() error {
			value, err := execute([]string{"mise", "which", "gradle", "--plugin"})
			if err != nil {
				return err
			}
			provider := strings.TrimSpace(value)
			if err := checkBinary(execute, project, provider, "gradle"); err != nil {
				return err
			}
			value, err = execute([]string{"mise", "which", "gradle", "--version"})
			if err != nil {
				return err
			}
			version := strings.TrimSpace(value)
			if version == "" {
				return errors.New("mise returned no Gradle version")
			}
			mise = object{"status": "configured", "version": version, "provider": provider}
			return nil
		}()
		if err != nil {
			mise["error"] = err.Error()
		}
	}
	result := object{"id": "gradle", "required": true, "title": "Project Gradle Wrapper or mise installation", "status": "failed",
		"evidence": object{"wrapper": wrapper, "mise": mise}, "version": nil}
	versions := map[any]bool{}
	hasVersion := false
	for _, method := range []object{wrapper, mise} {
		if method["status"] == "configured" {
			versions[method["version"]] = true
			hasVersion = hasVersion || method["version"] != nil
			result["status"] = "satisfied"
		}
	}
	if len(versions) == 1 {
		for version := range versions {
			result["version"] = version
		}
	}
	if !hasVersion {
		return result
	}
	stable, err := latestGradle()
	if err != nil {
		result["release_error"] = err.Error()
		return result
	}
	result["latest_stable"] = stable
	for _, method := range []object{wrapper, mise} {
		if match := gradleVersion.FindStringSubmatch(asString(method["version"])); match != nil {
			comparison := compareVersions(stable, match[1])
			if comparison > 0 || (comparison == 0 && previewGradle.MatchString(match[2])) {
				method["suggested_version"] = stable
			}
		}
	}
	return result
}

func latestGradle() (string, error) {
	raw, err := releaseMetadata(gradleRelease)
	if err != nil {
		return "", err
	}
	value, err := decodeJSON(raw, nil)
	if err != nil {
		return "", err
	}
	release := asObject(value)
	version := asString(release["version"])
	invalid := errors.New("Could not confirm the current stable Gradle release")
	if release["current"] != true || !stableGradle.MatchString(version) {
		return "", invalid
	}
	for _, flag := range []string{"broken", "snapshot", "nightly", "releaseNightly", "activeRc", "rcFor", "milestoneFor"} {
		switch release[flag] {
		case nil, false, "":
		default:
			return "", invalid
		}
	}
	return version, nil
}
