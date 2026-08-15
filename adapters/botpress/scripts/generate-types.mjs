import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { generatePluginImplementation } from "@botpress/cli/dist/code-generation/index.js";
import { definition } from "../.codegen/definition.js";

const files = await generatePluginImplementation(definition);
for (const file of files) {
  const target = resolve(".botpress", file.path);
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, file.content, "utf8");
  console.log(target);
}
