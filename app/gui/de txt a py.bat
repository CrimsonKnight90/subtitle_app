@echo off
echo Cambiando extensiones .txt a .py en la carpeta actual...
for %%f in (*.txt) do (
    ren "%%f" "%%~nf.py"
)
echo Listo.