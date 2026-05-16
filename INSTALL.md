# Installing DimagX CLI

Follow these steps to set up the futuristic `dimagx` command on your system.

## 1. Install Dependencies

Ensure you have all the required libraries installed:

```bash
pip install -r requirements.txt
```

Or if you are developing locally:

```bash
pip install -e .
```

## 2. Executable Setup

Since `dimagx` is defined in `pyproject.toml`, it will be available as a command once installed via `pip`. 

If you want to run it without installing, you can use:

```bash
python -m dimagx.cli
```

## 3. Bash/Zsh Alias Setup (Optional)

If you haven't installed it via pip, you can add an alias to your `~/.zshrc` or `~/.bashrc`:

```bash
alias dimagx='python3 /Users/syedhussainmehdi/Downloads/dimagx_release/dimagx/cli.py'
```

Then reload your shell:

```bash
source ~/.zshrc  # or ~/.bashrc
```

## 4. Run the Splash

Simply type:

```bash
dimagx
```

Enjoy the futuristic experience! 🚀
