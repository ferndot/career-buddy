# Getting started

In this tutorial you install career-buddy, import a resume, connect a language model and download a resume for a job posting. It takes about 20 minutes. The short version of the install is in the [README](../../README.md); this page goes through every step and shows what you should see.

## What you need

- A terminal: PowerShell on Windows, Terminal on macOS, any shell on Linux.
- [Git](https://git-scm.com/downloads).
- [uv](https://docs.astral.sh/uv/) 0.13 or newer. It installs Python 3.13 for you.
- [Node.js](https://nodejs.org/) 24 LTS (22.22.2 or newer also works) and [pnpm](https://pnpm.io/installation) 12.16.1.
- A resume as a PDF, DOCX, TXT or MD file, or its text.
- A language model, if you want career-buddy to write documents. A key for Anthropic or Google AI Studio works, and so does a local server such as Ollama.

## Step 1: Install uv

Windows (PowerShell):

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

You should see a version number. If the terminal says the command is not found, see [Troubleshooting](../../README.md#troubleshooting).

## Step 2: Install Node.js and pnpm

Install Node.js 24 LTS from [nodejs.org](https://nodejs.org/). Then install pnpm:

```bash
npm install -g pnpm@12.16.1
```

Check both:

```bash
node --version
```

```bash
pnpm --version
```

## Step 3: Get the code and install packages

```bash
git clone https://github.com/ferndot/career-buddy.git
```

```bash
cd career-buddy
```

```bash
uv sync
```

`uv sync` creates a `.venv` folder and installs Python 3.13 and the packages into it. You do not need to activate it. Put `uv run` in front of every Python command instead.

## Step 4: Install Chromium

PDF output needs a browser engine. This downloads Chromium once (about 150 MB):

```bash
uv run career-buddy install-browser
```

Skip this step if you will never download a PDF. Other formats do not need it.

## Step 5: Build the web UI

```bash
pnpm -C frontend install
```

```bash
pnpm -C frontend build
```

The UI is written to `src/career_buddy/web/static`. That folder is not in git, so you build it once after you clone, and again after you change the frontend.

## Step 6: Start the app

```bash
uv run career-buddy
```

The server starts at http://127.0.0.1:8000 and opens it in your browser. Leave the terminal open. Press Ctrl+C to stop.

You will see four screens in the sidebar: Sources, Career, Documents and Settings.

## Step 7: Import your resume

1. Open **Sources** and choose to add a source.
2. Drop a resume file into the box, or paste its text. Files can be PDF, DOCX, TXT or MD, up to 10 MB. A scanned PDF with no text layer cannot be read.
3. Give it a name if you pasted text, then import.

With no model connected, an offline reader finds the facts. It is quick but rough. With a model connected, the import runs in the background and the Sources screen shows its progress and a live log.

## Step 8: Review your career facts

Open **Career**. Your positions, achievements, skills and education are listed. Fix a wrong date or title, add anything missing, reorder entries, and merge duplicates that the page suggests. Documents are built from what is visible here, so correct it now.

## Step 9: Connect a model

Resume and letter writing needs a model. Open **Settings**, add a connection, press **Test**, then **Set active**. [Connect a model](../how-to/connect-a-model.md) lists the providers and addresses.

You can import and edit facts without a model. You cannot write documents without one.

## Step 10: Create a resume

Open **Documents** and choose **New document**. The wizard has five steps:

1. **Job posting.** Paste a link to the posting and wait for the text, or paste the text yourself. You can also choose to write without a posting. Only public `http` and `https` links work; for a page that needs JavaScript or a login, paste the text.
2. **Documents.** Choose a resume, a cover letter, or both.
3. **Missing requirements.** The model reads the posting and lists requirements that none of your facts mention. Answer each one.
4. **Template and preview.** Pick a template. A cover letter also needs the company and the role. Add directions for tone and length, and choose how many pages the resume should have. Read the draft and edit any text. Text marked for review could not be tied to your facts.
5. **Download.** Choose a format and download the file.

Documents you finish appear on the **Documents** screen, where you can open, download again, regenerate or delete them.

## Step 11: Run the tests

Back in the terminal, in the project folder:

```bash
uv run pytest -q
```

```bash
pnpm -C frontend test
```

Both should finish without errors, except the known failure and the skipped tests described in [Run the tests](../how-to/run-the-tests.md).

## What next

- [Connect a model](../how-to/connect-a-model.md)
- [Run with Docker](../how-to/run-with-docker.md)
- [Run the development servers](../how-to/run-the-dev-servers.md)
- [Configuration](../reference/configuration.md)
- [Architecture](../explanation/architecture.md)
