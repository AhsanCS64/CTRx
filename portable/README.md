# CTRx portable package (Windows Intel/AMD)

On the original PC, run from the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Export-Portable.ps1
```

Copy the resulting `CTRx-Portable` folder to the other PC. The folder includes
private `.env.docker` credentials: keep it private. No source, Python, Node or
separate PostgreSQL installation is needed. Install and open Docker Desktop
with Linux containers, then double-click `Start-CTRx.cmd`. First start imports
the images and opens the browser after health checks pass. Internet is required
for Neon. Double-click `Stop-CTRx.cmd` to stop while retaining media.

This package targets the same image CPU architecture as the exporting PC.
It uses Compose project `ctrx-portable`, with a separate persistent media volume.
Do not run it alongside the source stack on the same HTTP port. It does not
initialize or migrate databases. A failed schema check needs review in the source
project. All PCs using the same Neon URL share database changes, but their media
volumes are separate. Existing uploaded photos and documents are not exported.
Use one instance for uploads until shared media storage or a media transfer is
configured. Never use `down -v` for files you want to retain.

To install newer exported images, stop CTRx and run `docker load --input
ctrx-images.tar` in this folder before starting again. The launcher loads images
automatically only when one is missing. Docker Desktop must be running for both
launchers. If it cannot start, the window stays open with an error.
