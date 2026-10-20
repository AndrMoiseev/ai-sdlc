# Map — /kb-map and serve

Use the invocation defined in [runtime setup](runtime-setup.md).

1. Interpret the optional argument as the output path, defaulting to the project's
   `.gitmark/docs-map.html`. The map is a generated snapshot, not KB source.
2. Refresh with `G index`, then run `G map` or `G map -o "<output-path>"`.
   The project needs at least one Markdown document; on an empty project explain
   the gap and suggest the Build route instead of creating fictional docs.
3. Verify the output exists, report its full path and file/link counts. It contains
   an interactive tree, rendered documents and a force/radial link graph in one
   HTML file. Link the artifact for the user; open it if requested and supported.
4. For a requested local preview use `G serve -p 8799`, which serves `.gitmark/`
   on `127.0.0.1`. A custom output directory needs
   `G serve --directory "<output-parent>" -p 8799`; use the actual filename in the
   URL. Keep the server in a managed background session; on Windows hide any
   helper window. Report the URL and how to stop that session. Serve is long-running,
   so don't block completion waiting for it to exit.

Opening the HTML directly requires no HTTP server or external service. Regenerate
after documentation changes; the HTML does not watch source files.
