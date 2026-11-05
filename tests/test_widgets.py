import os
import subprocess
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVA_EXE = os.path.join(REPO_ROOT, "nova.exe")


def test_nss_pseudo_classes_parsing():
    """Verify that NSS parses :hover and :active pseudo-class rules into prefixed property maps."""
    test_nss = os.path.join(REPO_ROOT, "tests", "test_pseudo.nss")
    test_nv = os.path.join(REPO_ROOT, "tests", "test_nss_pseudo_run.nv")

    with open(test_nss, "w", encoding="utf-8") as f:
        f.write(""".btn {
    bg: #313244;
    color: #ffffff;
}

.btn:hover {
    bg: #45475a;
    color: #89b4fa;
}

.btn:active {
    bg: #181825;
}

#save:hover {
    border: 2;
}
""")

    with open(test_nv, "w", encoding="utf-8") as f:
        f.write('''import nss

st = nss.nss_load("tests/test_pseudo.nss")
if st.has("CLS__btn") == 1 {
    print("has CLS__btn: 1")
}
if st.has("CLS_HOVER__btn") == 1 {
    print("has CLS_HOVER__btn: 1")
}
if st.has("CLS_ACTIVE__btn") == 1 {
    print("has CLS_ACTIVE__btn: 1")
}
if st.has("ID_HOVER__save") == 1 {
    print("has ID_HOVER__save: 1")
}

hov = st.get("CLS_HOVER__btn")
print("hov bg: " + hov.get("hover-background-color"))
print("hov color: " + hov.get("hover-color"))
''')

    try:
        res = subprocess.run(
            [NOVA_EXE, "run", test_nv],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT
        )
        assert res.returncode == 0, f"Compilation/Execution failed:\n{res.stderr}\n{res.stdout}"
        assert "has CLS__btn: 1" in res.stdout
        assert "has CLS_HOVER__btn: 1" in res.stdout
        assert "has CLS_ACTIVE__btn: 1" in res.stdout
        assert "has ID_HOVER__save: 1" in res.stdout
        assert "hov bg: #45475a" in res.stdout
        assert "hov color: #89b4fa" in res.stdout
    finally:
        if os.path.exists(test_nss):
            os.remove(test_nss)
        if os.path.exists(test_nv):
            os.remove(test_nv)
        exe = test_nv.replace(".nv", ".exe")
        if os.path.exists(exe):
            os.remove(exe)


@pytest.mark.skipif(os.name != "nt", reason="Native Win32 GDI GUI is Windows-specific")
def test_gui_widgets_showcase():
    """Verify that the full widgets demo with checkboxes, toggles, sliders, dropdowns, and canvas compiles and runs cleanly."""
    demo_src = os.path.join(REPO_ROOT, "examples", "gui_widgets_demo.nv")
    assert os.path.isfile(demo_src), f"Missing {demo_src}"

    res = subprocess.run(
        [NOVA_EXE, "run", demo_src, "--test"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REPO_ROOT
    )
    assert res.returncode == 0, f"Widgets showcase execution failed:\n{res.stderr}\n{res.stdout}"
    assert "Demo completed successfully!" in res.stdout


@pytest.mark.skipif(os.name != "nt", reason="Native Win32 GDI GUI is Windows-specific")
def test_gui_input_showcase():
    """Verify that the interactive live input and screen print demo compiles and runs cleanly."""
    demo_src = os.path.join(REPO_ROOT, "examples", "gui_input_demo.nv")
    assert os.path.isfile(demo_src), f"Missing {demo_src}"

    res = subprocess.run(
        [NOVA_EXE, "run", demo_src, "--test"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REPO_ROOT
    )
    assert res.returncode == 0, f"Input showcase execution failed:\n{res.stderr}\n{res.stdout}"
    assert "Demo completed successfully!" in res.stdout


@pytest.mark.skipif(os.name != "nt", reason="Native Win32 GDI GUI is Windows-specific")
def test_gui_input_click_action():
    """Verify that onClick: 'submit' and onClick: 'clear' transfer and reset text correctly."""
    test_nv = os.path.join(REPO_ROOT, "tests", "test_click_action_run.nv")
    with open(test_nv, "w", encoding="utf-8") as f:
        f.write('''import gui

target = gui.txt("", "target", "Initial", {})
source = gui.input_field("", "source", "Placeholder", {})
source.text = "Hello Nova Action"

submit_b = gui.btn("btn-primary", "sub_id", "submit", "Submit", {
    "source": source,
    "target": target,
    "prefix": "Text: "
})

clear_b = gui.btn("btn-secondary", "clr_id", "clear", "Clear", {
    "target": target
})

gui.dispatchAction(submit_b, submit_b.on_click_id)
if target.text == "Text: Hello Nova Action" {
    print("SUBMIT_PASSED: " + target.text)
}

gui.dispatchAction(clear_b, clear_b.on_click_id)
if target.text == "" {
    print("CLEAR_PASSED")
}
''')

    try:
        res = subprocess.run(
            [NOVA_EXE, "run", test_nv],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT
        )
        assert res.returncode == 0, f"Execution failed:\n{res.stderr}\n{res.stdout}"
        assert "SUBMIT_PASSED: Text: Hello Nova Action" in res.stdout
        assert "CLEAR_PASSED" in res.stdout
    finally:
        if os.path.exists(test_nv):
            os.remove(test_nv)
        exe = test_nv.replace(".nv", ".exe")
        if os.path.exists(exe):
            os.remove(exe)


@pytest.mark.skipif(os.name != "nt", reason="Native Win32 GDI GUI is Windows-specific")
def test_declarative_app_demo_suite():
    """Verify that the Stage 1 high-level declarative GUI suite demo compiles and executes cleanly."""
    demo_src = os.path.join(REPO_ROOT, "examples", "declarative_app_demo.nv")
    assert os.path.isfile(demo_src), f"Missing {demo_src}"

    res = subprocess.run(
        [NOVA_EXE, "run", demo_src, "--test"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REPO_ROOT
    )
    assert res.returncode == 0, f"Declarative app suite execution failed:\n{res.stderr}\n{res.stdout}"


@pytest.mark.skipif(os.name != "nt", reason="Native Win32 GDI GUI is Windows-specific")
def test_reactive_state_demo_suite():
    """Verify that the Stage 2 reactive state architecture demo compiles and runs in test mode."""
    demo_src = os.path.join(REPO_ROOT, "examples", "reactive_state_demo.nv")
    assert os.path.isfile(demo_src), f"Missing {demo_src}"

    res = subprocess.run(
        [NOVA_EXE, "run", demo_src, "--test"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REPO_ROOT
    )
    assert res.returncode == 0, f"Reactive state demo execution failed:\n{res.stderr}\n{res.stdout}"


@pytest.mark.skipif(os.name != "nt", reason="Native Win32 GDI GUI is Windows-specific")
def test_reactive_state_unit():
    """Verify StateInt, StateStr, two-way bindings, and increment/reset action handlers."""
    test_nv = os.path.join(REPO_ROOT, "tests", "test_reactive_state_unit.nv")
    with open(test_nv, "w", encoding="utf-8") as f:
        f.write('''import gui

# 1. StateInt and Observer binding
count = gui.StateInt(10)
label = gui.Text("", {"bind": count, "prefix": "Count: ", "suffix": " items"})
if label.text == "Count: 10 items" {
    print("INITIAL_INT_BIND_PASSED")
}

# 2. StateStr and Observer binding
name = gui.StateStr("Nova")
input_w = gui.Input("", {"bind": name})
if input_w.text == "Nova" {
    print("INITIAL_STR_BIND_PASSED")
}

# 3. Direct State Mutation
gui.state_set_int(count, 42)
if label.text == "Count: 42 items" {
    print("SET_INT_PASSED")
}

gui.state_set_str(name, "SuperNova")
if input_w.text == "SuperNova" {
    print("SET_STR_PASSED")
}

# 4. Action Dispatch
inc_btn = gui.Button("Add", 1, {"action": "increment", "state": count})
reset_btn = gui.Button("Reset", 2, {"action": "reset", "state": count})

gui.dispatchAction(inc_btn, 1)
if count.val_int == 43 and label.text == "Count: 43 items" {
    print("INCREMENT_ACTION_PASSED")
}

gui.dispatchAction(reset_btn, 2)
if count.val_int == 0 and label.text == "Count: 0 items" {
    print("RESET_ACTION_PASSED")
}
''')

    try:
        res = subprocess.run(
            [NOVA_EXE, "run", test_nv],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=REPO_ROOT
        )
        assert res.returncode == 0, f"Reactive unit execution failed:\n{res.stderr}\n{res.stdout}"
        assert "INITIAL_INT_BIND_PASSED" in res.stdout
        assert "INITIAL_STR_BIND_PASSED" in res.stdout
        assert "SET_INT_PASSED" in res.stdout
        assert "SET_STR_PASSED" in res.stdout
        assert "INCREMENT_ACTION_PASSED" in res.stdout
        assert "RESET_ACTION_PASSED" in res.stdout
    finally:
        if os.path.exists(test_nv):
            os.remove(test_nv)
        exe = test_nv.replace(".nv", ".exe")
        if os.path.exists(exe):
            os.remove(exe)


