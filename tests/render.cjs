const fs = require('node:fs');
const transform = require('@diplodoc/transform');
const plugins = require('@diplodoc/transform/lib/plugins');

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const tableAttributes = [];
const captureTables = (md) => {
    md.core.ruler.push('capture-table-attributes', (state) => {
        for (const token of state.tokens) {
            if (token.meta?.rawAttrs) {
                tableAttributes.push({type: token.type, attributes: token.meta.rawAttrs});
            }
        }
    });
};
const output = transform(input.source, {
    disableLiquid: true,
    ...input.options,
    plugins: [...plugins, captureTables],
});
output.tableAttributes = tableAttributes;
process.stdout.write(JSON.stringify(output));
