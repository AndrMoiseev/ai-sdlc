"""Compare a Gradle task's ordered detekt configuration with the project recommendations."""
from pathlib import Path
from zipfile import ZipFile

from ruamel.yaml import YAML


ASSETS = Path(__file__).resolve().parents[1] / "assets"
REFERENCE_VERSIONS = {"1": "1.23.8", "2": "2.0.0-alpha.6"}
VARIABLE_NAME_LIMIT = "naming.VariableMaxLength.maximumVariableNameLength"
# Across releases, apply the template values only for deliberate project overrides.
PROJECT_RULES = {
    "comments.AbsentOrWrongFileLicense.active",
    "comments.CommentOverPrivateFunction.active",
    "comments.CommentOverPrivateProperty.active",
    "comments.DeprecatedBlockTag.active",
    "comments.DocumentationOverPrivateFunction.active",
    "comments.DocumentationOverPrivateProperty.active",
    "comments.EndOfSentenceFormat.active",
    "comments.KDocReferencesNonPublicProperty.active",
    "comments.OutdatedDocumentation.active",
    "comments.UndocumentedPublicClass.active",
    "comments.UndocumentedPublicFunction.active",
    "comments.UndocumentedPublicProperty.active",
    "complexity.CognitiveComplexMethod.active",
    "complexity.ComplexInterface.active",
    "complexity.LabeledExpression.active",
    "complexity.MethodOverloading.active",
    "complexity.NamedArguments.active",
    "complexity.NestedScopeFunctions.active",
    "complexity.ReplaceSafeCallChainWithRun.active",
    "complexity.StringLiteralDuplication.active",
    "empty-blocks.EmptyClassBlock.active",
    "exceptions.ErrorUsageWithThrowable.active",
    "exceptions.NotImplementedDeclaration.active",
    "exceptions.ObjectExtendsThrowable.active",
    "exceptions.ThrowingExceptionInMain.active",
    "naming.BooleanPropertyNaming.active",
    "naming.FunctionMaxLength.active",
    "naming.FunctionMinLength.active",
    "naming.FunctionNameMaxLength.active",
    "naming.FunctionNameMinLength.active",
    "naming.LambdaParameterNaming.active",
    "naming.NonBooleanPropertyPrefixedWithIs.active",
    "naming.VariableMaxLength.active",
    VARIABLE_NAME_LIMIT,
    "naming.VariableMinLength.active",
    "performance.UnnecessaryInitOnArray.active",
    "performance.UnnecessaryPartOfBinaryExpression.active",
    "performance.UnnecessaryTypeCasting.active",
    "potential-bugs.CastNullableToNonNullableType.active",
    "potential-bugs.CastToNullableType.active",
    "potential-bugs.CharArrayToStringCall.active",
    "potential-bugs.Deprecation.active",
    "potential-bugs.DontDowncastCollectionTypes.active",
    "potential-bugs.ElseCaseInsteadOfExhaustiveWhen.active",
    "potential-bugs.ExitOutsideMain.active",
    "potential-bugs.ImplicitUnitReturnType.active",
    "potential-bugs.LateinitUsage.active",
    "potential-bugs.MissingPackageDeclaration.active",
    "potential-bugs.MissingSuperCall.active",
    "potential-bugs.MissingUseCall.active",
    "potential-bugs.NullCheckOnMutableProperty.active",
    "potential-bugs.NullableToStringCall.active",
    "potential-bugs.PropertyUsedBeforeDeclaration.active",
    "potential-bugs.UnconditionalJumpStatementInLoop.active",
    "potential-bugs.UnnamedParameterUse.active",
    "potential-bugs.UnnecessaryNotNullCheck.active",
    "style.BracesOnIfStatements.active",
    "style.BracesOnWhenStatements.active",
    "style.CanBeNonNullable.active",
    "style.CascadingCallWrapping.active",
    "style.ClassOrdering.active",
    "style.DataClassContainsFunctions.active",
    "style.DataClassShouldBeImmutable.active",
    "style.DoubleNegativeExpression.active",
    "style.DoubleNegativeLambda.active",
    "style.EqualsOnSignatureLine.active",
    "style.ExplicitCollectionElementAccessMethod.active",
    "style.ExpressionBodySyntax.active",
    "style.MandatoryBracesLoops.active",
    "style.MaxChainedCallsOnSameLine.active",
    "style.MaxLineLength.active",
    "style.ModifierOrder.active",
    "style.MultilineLambdaItParameter.active",
    "style.MultilineRawStringIndentation.active",
    "style.NewLineAtEndOfFile.active",
    "style.NoTabs.active",
    "style.OptionalUnit.active",
    "style.PreferToOverPairSyntax.active",
    "style.RangeUntilInsteadOfRangeTo.active",
    "style.RedundantConstructorKeyword.active",
    "style.RedundantExplicitType.active",
    "style.RedundantVisibilityModifier.active",
    "style.RedundantVisibilityModifierRule.active",
    "style.StringShouldBeRawString.active",
    "style.TrailingWhitespace.active",
    "style.TrimMultilineRawString.active",
    "style.UnnecessaryAnnotationUseSiteTarget.active",
    "style.UnnecessaryAny.active",
    "style.UnnecessaryBackticks.active",
    "style.UnnecessaryFullyQualifiedName.active",
    "style.UnnecessaryInnerClass.active",
    "style.UnnecessaryLet.active",
    "style.UnnecessaryReversed.active",
    "style.UntilInsteadOfRangeTo.active",
    "style.UnusedImport.active",
    "style.UnusedImports.active",
    "style.UseDataClass.active",
    "style.UseEmptyCounterpart.active",
    "style.UseIfEmptyOrIfBlank.active",
    "style.UseLet.active",
    "style.UseSumOfInsteadOfFlatMapSize.active",
}


def read_config(path):
    yaml = YAML(typ="safe")
    if path.suffix.lower() == ".jar":
        with ZipFile(path) as archive:
            data = yaml.load(archive.read("default-detekt-config.yml"))
    else:
        data = yaml.load(path)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return data


def rule_settings(config, groups):
    settings = {}
    for group in groups:
        section = config.get(group)
        if section is None:
            continue
        if not isinstance(section, dict):
            raise ValueError(f"Expected a mapping at {group}")
        entries = [(group, section)]
        entries.extend((f"{group}.{name}", value) for name, value in section.items()
                       if isinstance(value, dict))
        for name, entry in entries:
            if name == "naming.VariableMaxLength" and "maximumVariableNameLength" in entry:
                settings[VARIABLE_NAME_LIMIT] = int(str(entry["maximumVariableNameLength"]))
            value = entry.get("active")
            if value is None:
                continue
            if type(value) is not bool and value not in ("true", "false"):
                raise ValueError(f"Expected a boolean at {name}.active")
            settings[f"{name}.active"] = value is True or value == "true"
    return settings


def inspect_detekt(project_root, version, defaults, config, standalone, ktlint, accept):
    root = project_root.resolve(strict=True)
    major = version.split(".")[0]
    if major not in REFERENCE_VERSIONS:
        raise ValueError(f"Unsupported detekt version: {version}")
    if standalone and not config:
        raise ValueError("Standalone mode requires a project configuration file")

    common = read_config(ASSETS / "detekt.yml")
    groups = set(common)
    native = rule_settings(read_config(defaults), groups)
    if not native:
        raise ValueError("No built-in rule settings found in the supplied detekt defaults")
    template = rule_settings(common, groups)
    template.update(rule_settings(read_config(ASSETS / f"detekt-{major}.yml"), groups))
    if version == REFERENCE_VERSIONS[major]:
        if template.keys() != native.keys():
            raise ValueError(f"Rule list in the supplied defaults differs from detekt {version}")
        recommended = template
    else:
        recommended = native.copy()
        for key in PROJECT_RULES & native.keys() & template.keys():
            recommended[key] = template[key]
        for key in native:
            if key.startswith("coroutines.") or key.split(".")[1].startswith("Forbidden"):
                recommended[key] = False
    if ktlint:
        group = "formatting" if major == "1" else "ktlint"
        groups.add(group)
        native[f"{group}.active"] = True
        recommended[f"{group}.active"] = False

    explicit = {}
    for path in config:  # detekt gives the last file containing a key precedence.
        path = (root / path).resolve(strict=True)
        for key, value in rule_settings(read_config(path), groups).items():
            explicit[key] = (value, path)

    pin, differences = {}, {}
    matches = 0
    for key, wanted in sorted(recommended.items()):
        # Without the bundled defaults detekt enables rule sets and disables undeclared rules.
        fallback = native[key]
        if standalone and key.endswith(".active"):
            fallback = key.count(".") == 1
        current, source = explicit.get(key, (fallback, None))
        if current != wanted:
            differences[key] = {"current": current, "recommended": wanted,
                                "source": str(source) if source is not None else None}
        elif source is None or not source.is_relative_to(root):
            pin[key] = wanted
        else:
            matches += 1
    selected = set(accept)
    if selected == {"all"}:
        selected = differences.keys() | pin.keys()
    unknown = selected - recommended.keys()
    if unknown:
        raise ValueError(f"Unknown detekt setting or invalid selection: {', '.join(sorted(unknown))}")
    edits = {key: recommended[key] for key in sorted(selected) if key in pin or key in differences}
    yaml_edits = {}
    for key, value in edits.items():
        node = yaml_edits
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return {"project_root": str(root), "version": version, "explicit_matches": matches,
            "pin": pin, "differences": differences, "yaml_edits": yaml_edits}
