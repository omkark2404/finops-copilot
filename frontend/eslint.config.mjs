import {defineConfig,globalIgnores} from 'eslint/config'
import tseslint from 'typescript-eslint'
import hooks from 'eslint-plugin-react-hooks'
import a11y from 'eslint-plugin-jsx-a11y'
import unusedImports from 'eslint-plugin-unused-imports'
export default defineConfig([
  ...tseslint.configs.recommended,
  {files:['**/*.tsx'],...a11y.flatConfigs.recommended},
  {plugins:{'unused-imports':unusedImports,'react-hooks':hooks},rules:{
    'unused-imports/no-unused-imports':'error',
    '@typescript-eslint/no-explicit-any':'error',
    '@typescript-eslint/no-unused-vars':['error',{argsIgnorePattern:'^_',varsIgnorePattern:'^_'}],
    'react-hooks/rules-of-hooks':'error',
    'react-hooks/exhaustive-deps':'error',
  }},
  globalIgnores(['.next/**','playwright-report/**','test-results/**','next-env.d.ts']),
])
