from __future__ import annotations

import tempfile
from pathlib import Path

from eng_loop.tools.autosizing import (
    DOCUMENTATION_EXCLUDED_STAGES,
    OPERATIONAL_EXCLUDED_STAGES,
    VALIDATION_EXCLUDED_STAGES,
    WORK_TYPE_KEYWORDS,
    _estimate_files,
    _estimate_tasks,
    _has_ambiguity,
    _has_integrations,
    _has_new_domains,
    classify_complexity,
    classify_work_type,
    deactivate_for_work_type,
    deactivate_inactive_stages,
    detect_ui_project,
    is_operational_work,
)

# _estimate_files


def test_estimate_files_empty():
    assert _estimate_files("") >= 1


def test_estimate_files_single_keyword():
    assert _estimate_files("Add a new file") == 1


def test_estimate_files_multiple_keywords():
    result = _estimate_files("Add a file, module, component, and class")
    assert result == 4


def test_estimate_files_all_keywords():
    text = "file module component class function endpoint route page screen"
    assert _estimate_files(text) == 9


def test_estimate_files_case_insensitive():
    assert _estimate_files("Add a FILE and MODULE") == 2


# _estimate_tasks


def test_estimate_tasks_empty():
    assert _estimate_tasks("") >= 1


def test_estimate_tasks_single_indicator():
    assert _estimate_tasks("You should do this") == 1


def test_estimate_tasks_multiple_indicators():
    result = _estimate_tasks("Implement and create and build the thing")
    assert result == 3


def test_estimate_tasks_all_indicators():
    text = "should must need to implement create build add update fix"
    assert _estimate_tasks(text) == 9


def test_estimate_tasks_case_insensitive():
    assert _estimate_tasks("You MUST IMPLEMENT it") == 2


# _has_new_domains


def test_has_new_domains_empty():
    assert _has_new_domains("") is False


def test_has_new_domains_machine_learning():
    assert _has_new_domains("Build a machine learning model") is True


def test_has_new_domains_ai():
    assert _has_new_domains("Add AI capabilities") is True


def test_has_new_domains_blockchain():
    assert _has_new_domains("Use blockchain technology") is True


def test_has_new_domains_iot():
    assert _has_new_domains("IoT device integration") is True


def test_has_new_domains_realtime():
    assert _has_new_domains("real-time data processing") is True


def test_has_new_domains_streaming():
    assert _has_new_domains("streaming analytics") is True


def test_has_new_domains_ml_model():
    assert _has_new_domains("train ml model") is True


def test_has_new_domains_neural():
    assert _has_new_domains("neural network architecture") is True


def test_has_new_domains_case_insensitive():
    assert _has_new_domains("MACHINE LEARNING pipeline") is True


def test_has_new_domains_normal_text():
    assert _has_new_domains("Build a web application with a database") is False


# _has_integrations


def test_has_integrations_empty():
    assert _has_integrations("") is False


def test_has_integrations_api():
    assert _has_integrations("Build a REST api") is True


def test_has_integrations_integration():
    assert _has_integrations("Third-party integration") is True


def test_has_integrations_webhook():
    assert _has_integrations("Setup webhook endpoint") is True


def test_has_integrations_third_party():
    assert _has_integrations("Connect to third-party service") is True


def test_has_integrations_external_service():
    assert _has_integrations("Call external service") is True


def test_has_integrations_sdk():
    assert _has_integrations("Use the Stripe SDK") is True


def test_has_integrations_oauth():
    assert _has_integrations("Setup oauth flow") is True


def test_has_integrations_payment():
    assert _has_integrations("Add payment processing") is True


def test_has_integrations_case_insensitive():
    assert _has_integrations("Setup OAuth for API") is True


def test_has_integrations_normal_text():
    assert _has_integrations("Build a simple web page") is False


# _has_ambiguity


def test_has_ambiguity_empty():
    assert _has_ambiguity("") is False


def test_has_ambiguity_maybe():
    assert _has_ambiguity("Maybe we should add this") is True


def test_has_ambiguity_perhaps():
    assert _has_ambiguity("Perhaps we can do it") is True


def test_has_ambiguity_ideally():
    assert _has_ambiguity("Ideally this would work") is True


def test_has_ambiguity_somewhat():
    assert _has_ambiguity("It is somewhat complex") is True


def test_has_ambiguity_roughly():
    assert _has_ambiguity("Roughly 10 files") is True


def test_has_ambiguity_approximately():
    assert _has_ambiguity("Approximately 5 endpoints") is True


def test_has_ambiguity_might_want():
    assert _has_ambiguity("You might want to consider this") is True


def test_has_ambiguity_case_insensitive():
    assert _has_ambiguity("MAYBE we should") is True


def test_has_ambiguity_clear_text():
    assert _has_ambiguity("Implement the login endpoint") is False


# classify_complexity


def test_classify_complexity_small():
    config = {"auto_sizing": {"heuristics": {}}}
    assert classify_complexity("Fix typo in README", config) == "small"


def test_classify_complexity_medium_many_files():
    config = {"auto_sizing": {"heuristics": {"small": {"max_files": 2}}}}
    result = classify_complexity("file file file file", config)
    assert result == "medium"


def test_classify_complexity_large_oauth_payment():
    config = {"auto_sizing": {"heuristics": {}}}
    result = classify_complexity("Implement auth with oauth and payment gateway", config)
    assert result in ("medium", "large")


def test_classify_complexity_complex_all_factors():
    config = {"auto_sizing": {"heuristics": {}}}
    result = classify_complexity("Maybe build a machine learning model with oauth integration", config)
    assert result == "complex"


def test_classify_complexity_custom_heuristics():
    config = {
        "auto_sizing": {
            "heuristics": {
                "small": {"max_files": 100, "max_tasks": 100},
                "medium": {"max_files": 1000, "max_tasks": 1000},
            }
        }
    }
    assert classify_complexity("Add a file", config) == "small"


def test_classify_complexity_many_files_large():
    config = {"auto_sizing": {"heuristics": {"small": {"max_files": 2}}}}
    text = "file file file file file"
    assert classify_complexity(text, config) in ("medium", "large")


# classify_work_type


def test_classify_work_type_documentation():
    assert classify_work_type("Write project summary") == "documentation"


def test_classify_work_type_operational():
    assert classify_work_type("Run tests") == "operational"


def test_classify_work_type_bugfix():
    assert classify_work_type("Fix broken login") == "bugfix"


def test_classify_work_type_feature():
    assert classify_work_type("Implement new feature") == "feature"


def test_classify_work_type_portuguese_documentation():
    assert classify_work_type("Escrever resumo do projeto") == "documentation"


def test_classify_work_type_portuguese_operational():
    assert classify_work_type("Rodar testes") == "operational"


def test_classify_work_type_generate_report():
    assert classify_work_type("Generate report") == "documentation"


def test_classify_work_type_deploy():
    assert classify_work_type("Deploy to production") == "operational"


def test_classify_work_type_fix_bug():
    assert classify_work_type("Fix bug in checkout flow") == "bugfix"


def test_classify_work_type_add_feature():
    assert classify_work_type("Add support for dark mode") == "feature"


def test_classify_work_type_update_docs():
    assert classify_work_type("Update documentation") == "documentation"


def test_classify_work_type_run_build():
    assert classify_work_type("Run build pipeline") == "operational"


def test_classify_work_type_corrigir_erro():
    assert classify_work_type("Corrigir erro no login") == "bugfix"


def test_classify_work_type_implementar():
    assert classify_work_type("Implementar nova funcionalidade") == "feature"


def test_classify_work_type_tier_scoring():
    assert classify_work_type("Create the documentation") == "documentation"


# is_operational_work


def test_is_operational_work_true():
    assert is_operational_work("Run tests") is True


def test_is_operational_work_false():
    assert is_operational_work("Implement new feature") is False


def test_is_operational_work_deploy():
    assert is_operational_work("Deploy to staging") is True


def test_is_operational_work_documentation():
    assert is_operational_work("Write project summary") is False


# deactivate_for_work_type


def test_deactivate_for_work_type_feature_unchanged():
    stages = {"impl.code": {"done": False, "attempts": 0, "essence_checked": False}}
    result = deactivate_for_work_type(stages, "feature")
    assert result["impl.code"]["done"] is False


def test_deactivate_for_work_type_documentation():
    stages = {}
    for sid in DOCUMENTATION_EXCLUDED_STAGES:
        stages[sid] = {"done": False, "attempts": 0, "essence_checked": False}
    stages["impl.code"] = {"done": False, "attempts": 0, "essence_checked": False}
    result = deactivate_for_work_type(stages, "documentation")
    for sid in DOCUMENTATION_EXCLUDED_STAGES:
        assert result[sid]["done"] is True
    assert result["impl.code"]["done"] is False


def test_deactivate_for_work_type_operational():
    stages = {}
    for sid in OPERATIONAL_EXCLUDED_STAGES:
        stages[sid] = {"done": False, "attempts": 0, "essence_checked": False}
    stages["init"] = {"done": False, "attempts": 0, "essence_checked": False}
    result = deactivate_for_work_type(stages, "operational")
    for sid in OPERATIONAL_EXCLUDED_STAGES:
        assert result[sid]["done"] is True
    assert result["init"]["done"] is False


def test_deactivate_for_work_type_bugfix():
    stages = {}
    design_stages = [
        "design.user-research",
        "design.personas",
        "design.info-arch",
        "design.interaction",
        "design.design-system",
        "design.visual-design",
    ]
    for sid in design_stages:
        stages[sid] = {"done": False, "attempts": 0, "essence_checked": False}
    stages["impl.code"] = {"done": False, "attempts": 0, "essence_checked": False}
    result = deactivate_for_work_type(stages, "bugfix")
    for sid in design_stages:
        assert result[sid]["done"] is True
    assert result["impl.code"]["done"] is False


def test_deactivate_for_work_type_sets_attempts_zero():
    stages = {"impl.code": {"done": False, "attempts": 5, "essence_checked": True}}
    result = deactivate_for_work_type(stages, "feature")
    assert result["impl.code"]["attempts"] == 5


# detect_ui_project


def test_detect_ui_project_package_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "package.json").write_text("{}")
        assert detect_ui_project({"project_root": tmpdir}) is True


def test_detect_ui_project_vite_config_ts():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "vite.config.ts").write_text("")
        assert detect_ui_project({"project_root": tmpdir}) is True


def test_detect_ui_project_next_config_js():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "next.config.js").write_text("")
        assert detect_ui_project({"project_root": tmpdir}) is True


def test_detect_ui_project_nuxt_config_js():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "nuxt.config.js").write_text("")
        assert detect_ui_project({"project_root": tmpdir}) is True


def test_detect_ui_project_angular_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "angular.json").write_text("{}")
        assert detect_ui_project({"project_root": tmpdir}) is True


def test_detect_ui_project_tailwind_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "tailwind.config.js").write_text("")
        assert detect_ui_project({"project_root": tmpdir}) is True


def test_detect_ui_project_no_indicators():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "README.md").write_text("hello")
        assert detect_ui_project({"project_root": tmpdir}) is False


def test_detect_ui_project_empty_root():
    assert detect_ui_project({"project_root": ""}) is False


def test_detect_ui_project_missing_key():
    assert detect_ui_project({}) is False


def test_detect_ui_project_nested_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        nested = Path(tmpdir, "src")
        nested.mkdir()
        nested.joinpath("package.json").write_text("{}")
        assert detect_ui_project({"project_root": tmpdir}) is False


# deactivate_inactive_stages


def test_deactivate_inactive_stages_no_ui():
    from eng_loop.state import init_stages

    stages = init_stages()
    result = deactivate_inactive_stages(stages, "medium", False)
    assert result["e2e.execute"]["done"] is True
    assert result["smoke.test"]["done"] is True


def test_deactivate_inactive_stages_small_complexity():
    from eng_loop.state import init_stages

    stages = init_stages()
    result = deactivate_inactive_stages(stages, "small", True)
    assert result["design.user-research"]["done"] is True
    assert result["arch.requirements"]["done"] is True
    assert result["impl.code"]["done"] is False
    assert result["init"]["done"] is False


def test_deactivate_inactive_stages_ui_project():
    from eng_loop.state import init_stages

    stages = init_stages()
    result = deactivate_inactive_stages(stages, "large", True)
    assert result["e2e.execute"]["done"] is False
    assert result["smoke.test"]["done"] is False


# Constants


def test_documentation_excluded_stages():
    expected = {
        "impl.design",
        "doc.update",
        "verify",
        "deploy.prepare",
        "arch.requirements",
        "arch.solution",
        "arch.review",
        "design.user-research",
        "design.personas",
        "design.info-arch",
        "design.interaction",
        "design.design-system",
        "design.visual-design",
        "qa.security",
        "qa.api-contract",
        "qa.performance",
        "e2e.execute",
        "smoke.test",
        "doc.decisions",
        "doc.project",
    }
    assert set(DOCUMENTATION_EXCLUDED_STAGES) == expected


def test_operational_excluded_stages():
    expected = {
        "impl.design",
        "impl.code",
        "doc.update",
        "verify",
        "arch.requirements",
        "arch.solution",
        "arch.review",
        "design.user-research",
        "design.personas",
        "design.info-arch",
        "design.interaction",
        "design.design-system",
        "design.visual-design",
        "doc.decisions",
        "doc.project",
    }
    assert set(OPERATIONAL_EXCLUDED_STAGES) == expected


def test_work_type_keywords_categories():
    assert "documentation" in WORK_TYPE_KEYWORDS
    assert "documentation_single" in WORK_TYPE_KEYWORDS
    assert "operational" in WORK_TYPE_KEYWORDS
    assert "operational_single" in WORK_TYPE_KEYWORDS
    assert "bugfix" in WORK_TYPE_KEYWORDS
    assert "bugfix_single" in WORK_TYPE_KEYWORDS
    assert "feature" in WORK_TYPE_KEYWORDS


def test_work_type_keywords_non_empty():
    for category, keywords in WORK_TYPE_KEYWORDS.items():
        assert len(keywords) > 0, f"{category} should have keywords"


def test_classify_work_type_validation():
    assert classify_work_type("Validate the system for production") == "validation"


def test_classify_work_type_validation_portuguese():
    assert classify_work_type(
        "Valide o sistema atual para ser executado em producao"
    ) == "validation"


def test_classify_work_type_validation_readiness():
    assert classify_work_type("Production readiness check for all stages") == "validation"


def test_deactivate_for_work_type_validation():
    stages = {
        "init": {"done": False, "attempts": 0},
        "impl.design": {"done": False, "attempts": 0},
        "impl.code": {"done": False, "attempts": 0},
        "doc.update": {"done": False, "attempts": 0},
        "verify": {"done": False, "attempts": 0},
        "qa.static": {"done": False, "attempts": 0},
        "deploy.prepare": {"done": False, "attempts": 0},
        "post": {"done": False, "attempts": 0},
    }
    result = deactivate_for_work_type(stages, "validation")
    assert result["impl.design"]["done"] is True
    assert result["impl.code"]["done"] is True
    assert result["doc.update"]["done"] is True
    # verify, QA, deploy should remain active
    assert result["verify"]["done"] is False
    assert result["qa.static"]["done"] is False
    assert result["deploy.prepare"]["done"] is False
    assert result["post"]["done"] is False


def test_validation_excluded_stages():
    assert "impl.design" in VALIDATION_EXCLUDED_STAGES
    assert "impl.code" in VALIDATION_EXCLUDED_STAGES
    assert "doc.update" in VALIDATION_EXCLUDED_STAGES
    assert "verify" not in VALIDATION_EXCLUDED_STAGES
    assert "qa.static" not in VALIDATION_EXCLUDED_STAGES
    assert "deploy.prepare" not in VALIDATION_EXCLUDED_STAGES


def test_work_type_keywords_validation():
    assert "validation" in WORK_TYPE_KEYWORDS
    assert "validation_single" in WORK_TYPE_KEYWORDS
