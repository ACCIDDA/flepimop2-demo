# Project_Template

Welcome to the Atlantic Coast Center for Infectious Disease Dynamics and Analytics (ACCIDDA) template project repository for the `Flexible Epidemic Modeling Pipeline 2` pipeline. “FlepiMoP2” provides a framework for quickly implmenting and simulating infectious disease models to project epidemic trajectories and their healthcare impacts, and to evaluate the impact of potential interventions.

We recommend that most users clone this repo to ensure that their projects are well organized.  

## General guidelines for keeping clean project repositories:
    - Use version control / GitHub to archive old versions rahter than an active archive folder
    - Avoid duplication of model input across different configs unless absolutely nessecary 
    - Make single PDF figures for diagnostic plotting which compile your results rather than `PNG` or `JPEG` spaghetti
    - Keep all input data where `csv`, `parquet` etc. files stored in one common parent folder such as `./Model_Input/Data/Time_Series/Vaccination` and `./Model_Input/Data/Population_Structure/Initial_Conditions`
    - Similalry, keep good hygene around plugins such as `./Model_Input/Plugins/Initial_Conditions.py`



