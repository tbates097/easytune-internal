IF EXIST "pylintOutput.txt" (del "pylintOutput.txt")
pylint process_sinefrd_folder.py >> "pylintOutput.txt"
pylint process_multisinefrd_folder.py >> "pylintOutput.txt"
pylint process_whitenoisefrd_file.py >> "pylintOutput.txt"