@echo off
echo Cambiando extensiones .py a .txt en la carpeta actual...
for %%f in (*.py) do (
    ren "%%f" "%%~nf.txt"
)
echo Listo.