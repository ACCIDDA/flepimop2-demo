# Initialize a New Project Using `flepimop2`

Use this template to create a project repository for work using the [Flexible Epidemic Modeling Pipeline 2 (`flepimop2`)](https://github.com/ACCIDDA/flepimop2).

This template provides the recommended directory structure, default GitHub actions workflows, and getting started guidance.

To get started using this template follow the [Getting Started](#getting-started) section below.

## Getting Started

### Prerequisites

This getting started guide assumes that you have the following installed:

* [`git`](https://git-scm.com/): Version control system for tracking changes to your project files and collaborating with others.
* [`conda`](https://anaconda.org/): Package and environment manager for creating isolated Python/R environments with all required dependencies.
* [`just`](https://just.systems/): Command runner for executing common project tasks like setting up environments, running tests, and building configs.
* [`air`](https://posit-dev.github.io/air/): R code formatter and linter for maintaining consistent R code style in postprocessing scripts. Unlike other linting tools used by this project template this tool cannot be managed via `conda`.

### Clone This Template

It's strongly recommended that git is used to version work within the project. The first step is to create a blank git repository with your git hosting platform of choice. For example let's say your username/organization is `colonel-sam-daniels` and you want to work on `motaba`, then

```bash
git clone git@github.com:ACCIDDA/FlepiMoP2_Project_Template.git motaba
cd motaba
git remote set-url origin git@github.com:colonel-sam-daniels/motaba.git
```

This will create a clone of this repository and correct the `origin` remote to point to your blank repository. You can now `git push` your changes to your repository.

### Directory Structure

```bash
> tree -a -I '.git'
.
├── .gitattributes
├── .github
│   └── workflows
│       └── ci.yaml
├── .gitignore
├── .yamllint.yaml
├── air.toml
├── batch
│   └── .gitkeep
├── configs
│   └── built
│       └── .gitignore
├── environment.yaml
├── justfile
├── LICENSE
├── model_input
│   ├── data
│   │   └── .gitkeep
│   └── plugins
│       └── .gitkeep
├── postprocessing
│   └── .gitkeep
├── README.md
└── ruff.toml

10 directories, 15 files
```

* `.gitattributes`/`.gitignore`: These files contain general purpose settings/ignores recommended by this template. Namely the `.gitignore` excludes the `model_output/` directory which typically has outputs that are far too large to be tracked by git.
* `.github/`: Contains a GitHub actions workflow called "CI" in `ci.yaml` which runs `just ci`.
* `.yamllint.yaml`/`air.toml`/`ruff.toml`: These files contain the configuration for the YAML, R, & python linting tools used by this project template.
* `environment.yaml`: Conda environment specification that defines all Python and R dependencies for the project. By default it installs Python 3.10+, R 4.3+, the `flepimop2` package from GitHub, linting tools (`yamllint`, `ruff`), and Apache Arrow libraries (`pyarrow`, `r-arrow`) for efficient data interchange between Python and R. Running `conda env create -f environment.yaml` (or `just venv`) creates a reproducible environment ensuring all collaborators use the same package versions.
* `justfile`: This file defines the commands that are available via `just`. To see the commands that are available you can run `just --list`. The most important non-default commands are `just venv`, `just ci`.
* `batch/`: This directory should contain scripts for submitting batch jobs to slurm, AWS batch, etc.
* `configs/`: This directory should contain config parts/templates that are pieced together using `flepimop patch` and built configs (like those used for submission in an HPC job) should go under `configs/built/` which will not be tracked by git.
* `LICENSE`: This contains the license file for the repository, which is MIT. The MIT allows for both private use and modification of this template.
* `model_input/`: This directory contains inputs for running models, namely `data` for input data & time series and `plugins` for modular plugs to modify the behavior of `flepimop2`.
* `postprocessing/`: This directory should be the home for custom built scripts to manipulate the outputs of your model.
* `README.md`: This file contains this guide you are reading currently, but you should modify this to add details specific to your project especially if you have collaborators or are working on an open source project.

### Setting Up Your Development Environment

After cloning the template, you'll need to set up your local development environment:

1. *Create the conda environment*: Run `just venv` to create a conda environment in the `venv/` directory using the packages specified in `environment.yaml`. This may take several minutes as conda resolves dependencies and installs all required packages.
2. *Activate the environment*: Before working on your project, activate the conda environment with `conda activate ./venv`. You'll need to do this each time you start a new terminal session.
3. *Format and lint your code*: Run `just` (or `just default`) to automatically format and lint all YAML, Python, and R files in your project. This runs `yamllint`, `air format`, and `ruff format/check` to ensure your code follows consistent style guidelines.
4. *Run CI checks locally*: Before pushing changes, run `just ci` to verify your code passes all continuous integration checks. This command runs the same linting and formatting checks that the GitHub Actions workflow will run, but in check-only mode (no automatic fixes). If `just ci` passes locally, the CI workflow should pass on GitHub.

You can add more dependencies to your conda environment by adding them to the `environment.yaml` file and repeating the steps (1) & (2) above after running `just clean`.

## General Guidelines

- **Use version control**: As previously iterated in this guide, it is highly recommended that git is used to version control your projects to make it easier to review changes and restore to past versions of your model as needed.  
- **Avoid duplication**: Avoid duplicating files and folders and instead store common configuration parts in `configs/` or common data inputs in `model_input/data/`. 
- **Generate single-PDF diagnostic plots**: As opposed to producing several image plots (say one plot for each location or stratification) keep plots tidy by consolidating them into a one-PDF per a model run.
- **Maintain clean modular plugins**: One off plugins should be placed under `model_input/plugins/` and more complicated modules should have their own git repository.
