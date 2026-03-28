"""Preview styling for TestLog Editor."""

PREVIEW_STYLE = """
<style>
  body {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 15px;
    line-height: 1.7;
    color: #1a1a1a;
    max-width: 800px;
    margin: 0 auto;
    padding: 24px 32px;
  }

  h1, h2, h3, h4 {
    font-family: system-ui, sans-serif;
    font-weight: 600;
    margin-top: 1.6em;
    margin-bottom: 0.4em;
    color: #2563eb;
  }

  h1 { 
    font-size: 1.8em; 
    padding-bottom: 0.3em; 
  }
  h2 { 
    font-size: 1.4em; 
    padding-bottom: 0.2em; 
  }
  h3 { 
    font-size: 1.15em;
    padding-bottom: 0.1em;
  }

  p { margin: 0.8em 0; }

  code {
    font-family: 'Courier New', Courier, monospace;
    font-size: 0.88em;
    background: #e0e0e0;
    border: 1px solid #ccc;
    border-radius: 3px;
    padding: 1px 5px;
    color: #1a1a1a;
  }

  pre {
    margin: 1.5em 0;
    white-space: pre-wrap;
  }

  pre code {
    background: none;
    border: none;
    padding: 0;
    display: block;
    line-height: inherit;
    margin: 0;
    border-radius: 0;
  }

  table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    font-size: 0.95em;
  }

  th, td {
    border: 1px solid #ccc;
    padding: 8px 12px;
    text-align: left;
  }

  th {
    background: #f0f0f0;
    font-family: system-ui, sans-serif;
    font-weight: 600;
  }

  tr:nth-child(even) { background: #fafafa; }

  img {
    max-width: 100%;
    height: auto;
    border-radius: 4px;
    margin: 8px 0;
  }

  blockquote {
    border-left: 3px solid #ccc;
    margin: 1em 0;
    padding: 4px 16px;
    color: #555;
    font-style: italic;
  }

  hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 2em 0;
  }

  a { color: #0066cc; }
</style>
"""
