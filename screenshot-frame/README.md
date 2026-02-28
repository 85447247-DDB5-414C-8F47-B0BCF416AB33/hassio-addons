# Home Assistant Add-on: Screenshot to Samsung Frame

Render Home Assistant dashboards or any URL and send screenshots directly to Samsung Frame TV.

## Features

- Local upload to Samsung Frame TV
- Configurable resolution and zoom
- Multiple authentication methods (bearer, basic, custom headers)
- **Built‑in control dashboard** accessible via the add‑on page (`Open Web UI` button)

## Configuration

See the add-on configuration page for all options.  The dashboard is served on port
`5000` (customisable via the `api_port` configuration option / `API_PORT`
environment variable).  When the add‑on is installed, the Supervisor will show
an **Open Web UI** link; if you enable Home Assistant **Ingress** (highly
recommended, and the default), the dashboard will be displayed inside the
Home Assistant UI and you’ll be able to open it without exposing a raw port.

## Local development & testing

This repository includes a VS Code devcontainer that mirrors the environment
used by Home Assistant’s build system, making it trivial to run and debug the
add‑on locally.  To get started:

1. Install the [Remote - Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
   extension in VS Code.
2. Open this folder in VS Code.  When prompted, **Reopen in Container** (or use
   the command palette “Rebuild and Reopen in Container”).
3. After the container builds and starts you’ll have Supervisor and Home
   Assistant running; start the add‑on by executing the **Start Home Assistant**
   task (Terminal → Run Task).
4. Access the local Home Assistant instance at `http://localhost:7123/`; the
   add‑on will appear under **Local Add‑ons**.  You can edit files and the
   container will automatically pick up changes.

> **macOS / Colima users** – the container expects the Docker daemon socket at
> `/var/run/docker.sock`. Colima places its socket in
> `~/.colima/default/docker.sock`; the devcontainer.json already mounts that
> file into the container, but it must exist before the container starts.  Run
> `colima start` (and verify the socket exists) before opening the workspace.
> If you still see
> ```
> failed to connect to the docker API at unix:///var/run/docker.sock;
> check if the path is correct and if the daemon is running: dial unix
> /var/run/docker.sock: connect: no such file or directory
> ```
> then either create a symlink on the host (`ln -s ~/.colima/default/docker.sock
> /var/run/docker.sock`), or export the `DOCKER_HOST` variable inside the
> container:
> ```sh
> export DOCKER_HOST=unix://${HOME}/.colima/default/docker.sock
> ```
>
> **Note:** Colima’s Docker 29-series build includes `docker buildx` by default
> but the devcontainer’s slim image may not expose it.  if you get
> `docker: unknown command: docker buildx`, install the plugin inside the
> container with `apt update && apt install -y docker-buildx` or run `docker
> buildx install` after starting the container.

The `.devcontainer/devcontainer.json` and `.vscode/tasks.json` files are taken
from the official [home‑assistant/devcontainer](https://github.com/home-assistant/devcontainer)
repository and ensure that all necessary ports and volumes are mounted.  You
can also build and run the add‑on image yourself with the standard Docker
`builder` tool as described on the <https://developers.home-assistant.io/docs/apps/testing>
page.
