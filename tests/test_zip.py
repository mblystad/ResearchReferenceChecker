import zip


def test_pyinstaller_args_include_required_stdlib_hidden_imports():
    args = zip._pyinstaller_args()

    for module_name in zip.PYINSTALLER_HIDDEN_IMPORTS:
        assert module_name in args
