import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'src/api/types.gen.ts'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    },
  },
  {
    // shadcn/ui components are generated files that intentionally co-export
    // small helpers (variant maps, context hooks) alongside the component.
    // That's a deliberate shadcn convention, not a bug -- react-refresh's
    // "only export components" rule doesn't apply to generated code we
    // don't hand-author, so it's disabled here rather than reshaping the
    // files just to silence the warning.
    files: ['src/components/ui/**/*.{ts,tsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    // Test-only files are never loaded by the Vite dev server's fast-refresh
    // boundary, so the rule has nothing to protect here.
    files: ['src/test/**/*.{ts,tsx}', '**/*.test.{ts,tsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
)
