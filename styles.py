"""Preview styling for TestLog Editor."""

PREVIEW_STYLE = """
<style>
  body {
    font-family: 'Source Sans 3', 'Noto Sans', Arial, sans-serif;
    font-size: 17px;
    line-height: 1.34;
    color: #1a1a1a;
    margin: 0;
    padding: 4px 16px 12px;
  }

  p, li, td, th, blockquote {
    font-family: 'Source Sans 3', 'Noto Sans', Arial, sans-serif;
    font-size: 17px;
    line-height: 1.34;
  }

  h1, h2, h3, h4 {
    font-family: 'Source Sans 3', 'Noto Sans', Arial, sans-serif;
    font-weight: 700;
    margin-top: 1.6em;
    margin-bottom: 0.4em;
    color: #2563eb;
  }

  h1 { 
    font-size: 14px; 
    padding-bottom: 0.3em; 
  }
  h2 { 
    font-size: 13px; 
    padding-bottom: 0.2em; 
  }
  h3 { 
    font-size: 12px;
    padding-bottom: 0.1em;
  }
  h4 {
    font-size: 12px;
  }

  p { margin: 0.8em 0; }

  code {
    font-family: 'IBM Plex Mono', Consolas, 'Courier New', monospace;
    font-size: 1em;
    background: #3a3f46;
    border: 1px solid #4b5560;
    border-radius: 3px;
    padding: 1px 5px;
    color: #f5f7fa;
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
    font-size: 1em;
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

  a {
    color: #2563eb;
    text-decoration: underline;
  }

  #preview-content > :first-child {
    margin-top: 0 !important;
  }

  #preview-content > :last-child {
    margin-bottom: 0;
  }
</style>
"""
