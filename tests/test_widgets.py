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

target = gui.txt("Initial", {})
source = gui.input_field("Placeholder", {})
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

