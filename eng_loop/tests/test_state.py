from __future__ import annotations

from eng_loop.state import (
    STAGE_ORDER,
    all_active_stages_done,
    get_active_stages,
    get_max_attempts,
    make_initial_state,
    next_incomplete_stage,
)


def test_stage_order():
    assert len(STAGE_ORDER) == 26
    assert STAGE_ORDER[0] == "init"
    assert STAGE_ORDER[-1] == "post"


def test_initial_state():
    state = make_initial_state({}, {})
    assert state["status"] == "running"
    assert state["iteration"] == 0
    assert state["complexity"] == "unset"
    assert len(state["stages"]) == 26
    for sid in STAGE_ORDER:
        assert state["stages"][sid]["done"] is False
        assert state["stages"][sid]["attempts"] == 0


def test_active_stages_small():
    active = get_active_stages("small", False)
    assert "init" in active
    assert "impl.code" in active
    assert "verify" in active
    assert "post" in active
    assert "design.user-research" not in active
    assert "arch.requirements" not in active
    assert "qa.security" not in active
    assert "e2e.execute" not in active


def test_active_stages_medium():
    active = get_active_stages("medium", False)
    assert "arch.requirements" in active
    assert "arch.solution" in active
    assert "qa.security" in active
    assert "qa.api-contract" in active
    assert "doc.decisions" in active
    assert "doc.project" in active
    assert "design.user-research" not in active
    assert "arch.review" not in active
    assert "qa.performance" not in active


def test_active_stages_large():
    active = get_active_stages("large", True)
    assert "design.user-research" in active
    assert "design.visual-design" in active
    assert "e2e.execute" in active
    assert "smoke.test" in active
    assert "arch.review" not in active
    assert "qa.performance" not in active


def test_active_stages_complex():
    active = get_active_stages("complex", True)
    assert "arch.review" in active
    assert "qa.performance" in active
    assert "e2e.execute" in active
    assert "smoke.test" in active


def test_next_incomplete_stage():
    state = make_initial_state({}, {})
    state["complexity"] = "small"
    state["ui_project"] = False

    next_s = next_incomplete_stage(state)
    assert next_s == "init"

    state["stages"]["init"]["done"] = True
    next_s = next_incomplete_stage(state)
    assert next_s == "init.ideate"


def test_all_active_done():
    state = make_initial_state({}, {})
    state["complexity"] = "small"
    state["ui_project"] = False

    assert not all_active_stages_done(state)

    for sid in get_active_stages("small", False):
        state["stages"][sid]["done"] = True

    assert all_active_stages_done(state)


def test_max_attempts():
    config = {"constraints": {"max_impl_code_attempts": 3, "max_verify_attempts": 5}}
    assert get_max_attempts(config, "impl.code") == 3
    assert get_max_attempts(config, "verify") == 5
    assert get_max_attempts(config, "unknown.stage") == 2


if __name__ == "__main__":
    test_stage_order()
    test_initial_state()
    test_active_stages_small()
    test_active_stages_medium()
    test_active_stages_large()
    test_active_stages_complex()
    test_next_incomplete_stage()
    test_all_active_done()
    test_max_attempts()
    print("All tests passed.")
