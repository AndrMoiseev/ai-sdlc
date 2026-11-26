package setup

import (
	"errors"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

const typespecCompiler = "@typespec/compiler"

func typespec(args arguments) (object, error) {
	message := "Select a package directory inside the project"
	project, err := projectDirectory(args.value("project-root"), message)
	if err != nil {
		return nil, err
	}
	dir, err := projectDirectory(anchored(project, args.value("package-dir")), message)
	if err != nil {
		return nil, err
	}
	if !inside(project, dir) {
		return nil, errors.New(message)
	}
	result := object{"project_root": project, "package_dir": dir, "package": typespecCompiler, "status": "node_unavailable"}
	mise := checkMise(dir)
	execute := miseReader(dir, mise)
	if execute == nil {
		result["error"] = asObject(mise["evidence"])["error"]
		return result, nil
	}
	err = func() error {
		out, err := execute([]string{"mise", "which", "node"})
		if err != nil {
			return err
		}
		node := strings.TrimSpace(out)
		if !filepath.IsAbs(node) || !isFile(node) {
			return errors.New("mise did not resolve a Node executable")
		}
		runNode := func(args ...string) (string, error) {
			argv := append([]string{node}, args...)
			run, err := runProcess(dir, 10*time.Second, nil, argv)
			if err != nil {
				return "", err
			}
			if run.code != 0 {
				return "", commandExit{argv, run}
			}
			return strings.TrimSpace(run.stdout), nil
		}
		version, err := runNode("--version")
		if err != nil {
			return err
		}
		result["node_version"], result["status"] = version, "unverified"
		installed, pnp := "", false
		for current := dir; ; current = filepath.Dir(current) {
			manifest := filepath.Join(current, "package.json")
			if isFile(manifest) && result["declaration"] == nil {
				value, err := readJSON(manifest)
				if err != nil {
					return err
				}
				for _, section := range []string{"devDependencies", "dependencies", "optionalDependencies", "peerDependencies"} {
					if observed, ok := asObject(asObject(value)[section])[typespecCompiler]; ok {
						result["declaration"] = object{"manifest": manifest, "section": section, "version": observed}
						break
					}
				}
			}
			if local := filepath.Join(current, "node_modules", "@typespec", "compiler", "package.json"); installed == "" && isFile(local) {
				installed = local
			}
			pnp = pnp || isFile(filepath.Join(current, ".pnp.cjs")) || isFile(filepath.Join(current, ".pnp.js"))
			if current == project || current == filepath.Dir(current) {
				break
			}
		}
		if pnp {
			result["status"] = "check_with_yarn"
			return nil
		}
		if installed == "" {
			result["status"] = "missing"
			if result["declaration"] != nil {
				result["status"] = "restore"
			}
			return nil
		}
		metadata, err := readJSON(installed)
		if err != nil {
			return err
		}
		if asObject(metadata)["name"] != typespecCompiler {
			return errors.New("Unexpected package in the local TypeSpec compiler directory")
		}
		bin := asObject(asObject(metadata)["bin"])
		if _, ok := bin["tsp"]; !ok {
			return errors.New("'tsp'")
		}
		cliPath := anchored(filepath.Dir(installed), asString(bin["tsp"]))
		cli, err := filepath.EvalSymlinks(cliPath)
		if err != nil {
			if _, statErr := os.Stat(cliPath); statErr != nil {
				return fileError(statErr)
			}
			return fileError(err)
		}
		if !inside(resolve(filepath.Dir(installed)), cli) {
			return errors.New("The tsp entry point is outside its installed package")
		}
		version, ok := asObject(metadata)["version"].(string)
		if !ok {
			return errors.New("'version'")
		}
		result["package_version"] = version
		output, err := runNode(cli, "--version")
		if err != nil {
			return err
		}
		verified, _ := regexp.MatchString(`(?:^|[^\p{L}\p{N}_.+-])v?`+regexp.QuoteMeta(version)+`(?:$|[^\p{L}\p{N}_.+-])`, output)
		if !verified {
			return errors.New("Local tsp --version did not confirm the installed package version")
		}
		result["status"], result["version"] = "undeclared", version
		if result["declaration"] != nil {
			result["status"] = "installed"
		}
		return nil
	}()
	if err != nil {
		result["error"] = commandMessage(err)
	}
	return result, nil
}
