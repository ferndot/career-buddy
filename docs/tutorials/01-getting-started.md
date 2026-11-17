# Getting started

In this tutorial you start career-buddy, import a resume, connect a language model and download a resume for a job posting. It takes about 20 minutes. The short version of the install is in the [README](../../README.md); this page goes through every step and shows what you should see. If you want to change the code, do the [developer setup](#developer-setup) at the end instead of steps 1 to 3.

## What you need

- A terminal: PowerShell on Windows, Terminal on macOS, any shell on Linux.
- [Docker Desktop](https://docs.docker.com/get-docker/). On Linux, Docker Engine with the Compose plugin also works.
- A resume as a PDF, DOCX, TXT or MD file, or its text.
- A language model, if you want career-buddy to write documents. A key for Anthropic or Google AI Studio works, and so does a local server such as Ollama.

## Step 1: Install Docker Desktop

Install [Docker Desktop](https://docs.docker.com/get-docker/) and start it. Wait until it says Docker is running. Check it in a terminal:

```bash
docker --version
```

You should see a version number.

## Step 2: Get the code

Without Git: open https://github.com/ferndot/career-buddy, choose **Code**, then **Download ZIP**, and unzip it. Open a terminal in the unzipped folder. On Windows, open the folder in File Explorer, right-click an empty space and choose **Open in Terminal**.

With Git:

```bash
git clone https://github.com/ferndot/career-buddy.git
```

```bash
cd career-buddy
```

## Step 3: Start the app

```bash
docker compose up --build -d
```

The first run builds the app and takes a few minutes. Open http://localhost:8080 in your browser. You will see four screens in the sidebar: Sources, Career, Documents and Settings.

To stop the app, run `docker compose down`. Your data is in the `data` folder, so it is still there next time. See [Run with Docker](../how-to/run-with-docker.md).

## Step 4: Import your resume

1. Open **Sources** and choose to add a source.
2. Drop a resume file into the box, or paste its text. Files can be PDF, DOCX, TXT or MD, up to 10 MB. A scanned PDF with no text layer cannot be read.
3. Give it a name if you pasted text, then import.

With no model connected, an offline reader finds the facts. It is quick but rough. With a model connected, the import runs in the background and the Sources screen shows its progress and a live log.

## Step 5: Review your career facts

Open **Career**. Your positions, achievements, skills and education are listed. Fix a wrong date or title, add anything missing, reorder entries, and merge duplicates that the page suggests. Documents are built from what is visible here, so correct it now.

## Step 6: Connect a model

Resume and letter writing needs a model. Open **Settings**, add a connection, press **Test**, then **Set active**. [Connect a model](../how-to/connect-a-model.md) lists the providers and addresses.

You can import and edit facts without a model. You cannot write documents without one.

## Step 7: Create a resume

Open **Documents** and choose **New document**. The wizard has five steps:

1. **Job posting.** Paste a link to the posting and wait for the text, or paste the text yourself. You can also choose to write without a posting. Only public `http` and `https` links work; for a page that needs JavaScript or a login, paste the text.
2. **Documents.** Choose a resume, a cover letter, or both.
3. **Missing requirements.** The model reads the posting and lists requirements that none of your facts mention. Answer each one.
4. **Template and preview.** Pick a template. A cover letter also needs the company and the role. Add directions for tone and length, and choose how many pages the resume should have. Read the draft and edit any text. Text marked for review could not be tied to your facts.
5. **Download.** Choose a format and download the file.

Documents you finish appear on the **Documents** screen, where you can open, download again, regenerate or delete them.


## Developer setup

Use this instead of steps 1 to 3 if you want to change the code or run the tests. You need [Git](https://git-scm.com/downloads), [uv](https://docs.astral.sh/uv/) 0.13 or newer (it installs Python 3.13 for you), [Node.js](https://nodejs.org/) 24 LTS (22.22.2 or newer also works) and [pnpm](https://pnpm.io/installation) 12.16.1.

Install uv. Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS and Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new terminal and check it:

```bash
uv --version
```

If the terminal says the command is not found, see [Troubleshooting](../../README.md#troubleshooting). Install Node.js 24 LTS from [nodejs.org](https://nodejs.org/), then pnpm:

```bash
npm install -g pnpm@12.16.1
```

Get the code (step 2), then install the Python packages. `uv sync` creates a `.venv` folder. You do not need to activate it. Put `uv run` in front of every Python command instead.

```bash
uv sync
```

PDF output needs a browser engine. This downloads Chromium once (about 150 MB). Skip it if you will never download a PDF.

```bash
uv run career-buddy install-browser
```

Build the web UI. It is written to `src/career_buddy/web/static`, which is not in git, so build it once after you clone and again after you change the frontend.

```bash
pnpm -C frontend install
```

```bash
pnpm -C frontend build
```

Start the app. It runs at http://127.0.0.1:8000 and opens in your browser. Leave the terminal open. Press Ctrl+C to stop.

```bash
uv run career-buddy
```

Then continue with step 4. Run the tests from the project folder. Both should finish without errors, except the known failure and the skipped tests described in [Run the tests](../how-to/run-the-tests.md).

```bash
uv run pytest -q
```

```bash
pnpm -C frontend test
```

The `spec-ops` tool is separate. To install it and run `uv run spec-ops health`, see [Developer tools](../../README.md#developer-tools).

## What next

- [Connect a model](../how-to/connect-a-model.md)
- [Run with Docker](../how-to/run-with-docker.md)
- [Run the development servers](../how-to/run-the-dev-servers.md)
- [Configuration](../reference/configuration.md)
- [Architecture](../explanation/architecture.md)
