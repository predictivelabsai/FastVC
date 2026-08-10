# FastVC repository skills

## Product-tour GIF

Use the tracked walkthrough when the product navigation or agentic workflows
change. The capture script visits the key left-sidebar workspaces, exercises
representative specialist-agent, Copilot, analytics and round-model flows, and
publishes only frames that pass its HTTP, browser and visible-error checks.

```bash
PORT=5059 DIGEST_ENABLED=0 .venv/bin/python main.py
DEMO_BASE_URL=http://127.0.0.1:5059 .venv/bin/python scripts/capture_demo.py
bash scripts/build_demo_gif.sh
```

The builder reads `docs/demo/frames/manifest.txt`, writes
`docs/demo/fastvc-walkthrough.gif`, and copies the same bytes to
`static/product-demo.gif` for the public landing page. Never add a failed frame
manually to the manifest; fix the screen or leave it out of the GIF.
