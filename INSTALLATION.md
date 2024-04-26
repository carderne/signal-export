# Installation

## Windows

ABOUT THE TOOL & INSTALLATION

- You need to install Python to be able to run the Python executable "sigexport.exe"
- The Python executable "sigexport.exe" is downloaded from the Python Package Index (an online repository). The Python executable requires Docker Desktop to function, and it will automatically download a Docker image that is used in the process of extracting the Signal chat data.
- Docker Desktop needs the Windows feature WSL2 (Windows Subsystem for Linux) to work.

INSTALLATION STEPS

1. Installation of Windows WSL2
	- Go to the Start menu and search for "Turn Windows features on or off".
	- Select "Windows Subsystem for Linux" and click OK.
	- Open a PowerShell prompt and install WSL2 with: "wsl --install"

2. Install Docker Desktop
	- Download Docker Desktop [get it here: https://docs.docker.com/get-docker/]
	- Run the Docker setup file
	- Select the option "Use WSL 2 instead of Hyper-V (recommended)"
	
3. Install Python
	- Go to the Start menu and open the Microsoft Store
	- In the Microsoft Store, search for "Python"
	- Click on "Python 3.12" (or later) and then "Get"
	
4. Download the Python executable "sigexport.exe"
	- Start a PowerShell prompt
	- Download the package from the online repository with: "pip install signal-export"

5. Start the Python executable to extract chat history [NOTE: The path retrieval needs to be simplified!]
  - In a PowerShell prompt, change to the path below. NOTE: You might need to manually look under \Packages\ to find the correct subdirectory!
  - "cd c:\Users\<MyUserName>\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts\"
	- Run the command below, the target directory will be automatically created:
		.\sigexport.exe c:\Temp\MySignalExport

TROUBLESHOOTING

- You might need to manually update WSL in some circumstances. If so, use the link below:
     Install WSL 2 Kernel Update (x64)
     https://learn.microsoft.com/en-us/windows/wsl/install-manual#step-4---download-the-linux-kernel-update-package

    
