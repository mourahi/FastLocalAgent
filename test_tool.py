from app.core.tools.python_executor_tool import executor_python
from app.core.tools.windows_command_tool import executor_cmd

# Tester avec le code Python problématique
python_test_code = 'import shutil\nstat = .disk_usage("C:/")\nprint(f"{.free / (1024**3):.f} GB")'
print('Testing Python code:', repr(python_test_code))

# Appeler l'outil comme un StructuredTool
python_result = executor_python.invoke({"code": python_test_code, "timeout": 5})
print('Python result:', repr(python_result))

# Appeler l'outil de commande Windows
cmd_test_command = 'echo Bonjour depuis cmd'
print('Testing Windows command:', repr(cmd_test_command))
cmd_result = executor_cmd.invoke({"command": cmd_test_command, "timeout": 5})
print('Command result:', repr(cmd_result))
