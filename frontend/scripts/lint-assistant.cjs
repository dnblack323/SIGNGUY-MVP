// Lint the assistant integration using the same ESLint implementation as CRA's build.
const path = require("path");
const craRoot = path.dirname(require.resolve("react-scripts/package.json"));
const resolve = (name) => require.resolve(name, { paths: [craRoot] });
const { ESLint } = require(resolve("eslint"));
(async () => {
  const eslint = new ESLint({ useEslintrc: false, resolvePluginsRelativeTo: craRoot,
    baseConfig: { extends: [resolve("eslint-config-react-app"), resolve("eslint-config-react-app/jest"), "plugin:react-hooks/recommended"] } });
  const results = await eslint.lintFiles(["src/App.js", "src/components/assistant/*.jsx", "src/lib/businessAssistant.js", "src/__tests__/AssistantSession.test.jsx", "src/__tests__/AssistantVoiceStageC.test.jsx", "src/__tests__/BusinessAssistantPage.test.jsx"]);
  console.log((await eslint.loadFormatter("stylish")).format(results));
  const errors = results.reduce((n, result) => n + result.errorCount, 0);
  const warnings = results.reduce((n, result) => n + result.warningCount, 0);
  console.log(`Assistant ESLint: ${errors} errors, ${warnings} warnings`);
  process.exitCode = errors || warnings ? 1 : 0;
})().catch((error) => { console.error(error); process.exitCode = 1; });
