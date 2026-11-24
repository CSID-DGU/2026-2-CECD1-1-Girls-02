import { FileBlob, PresentationFile } from "file:///C:/Program%20Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1119-907-0_26.1119.907.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const source = "C:\\Users\\20231\\Documents\\카카오톡 받은 파일\\판넬샘플.pptx";
const presentation = await PresentationFile.importPptx(await FileBlob.load(source));
const inspected = await presentation.inspect({
  kind: "slide,textbox,shape,image",
  maxChars: 30000,
});
console.log(inspected.ndjson ?? inspected);
