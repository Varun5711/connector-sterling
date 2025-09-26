FROM mcr.microsoft.com/windows/servercore:ltsc2019

SHELL ["powershell", "-Command", "$ErrorActionPreference = 'Stop';"]

WORKDIR C:\sterling

COPY SterlingInstaller\SterlingSetup.exe C:\sterling\SterlingSetup.exe
COPY connector C:\sterling\connector
COPY config\config.yaml C:\sterling\config\config.yaml
COPY bootstrap.ps1 C:\sterling\bootstrap.ps1

RUN Set-ExecutionPolicy Bypass -Scope Process -Force; \
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; \
    iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))

RUN choco install -y python --version=3.10.*/params:NoPath

ENV PATH="C:\\Python310;C:\\Python310\\Scripts;${env:PATH}"

RUN python -m pip install --upgrade pip
RUN python -m pip install -r C:\sterling\connector\requirements.txt

RUN if (Test-Path C:\sterling\SterlingSetup.exe) { \
      Start-Process -FilePath C:\sterling\SterlingSetup.exe -ArgumentList '/quiet','/norestart' -Wait; \
    } else { Write-Output 'Sterling installer not found - skipping install in image.' }

EXPOSE 5000

ENTRYPOINT ["powershell", "C:\\sterling\\bootstrap.ps1"]