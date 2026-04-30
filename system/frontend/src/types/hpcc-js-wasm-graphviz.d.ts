declare module "@hpcc-js/wasm/graphviz" {
  export class Graphviz {
    static load(): Promise<Graphviz>;
    dot(dotSource: string, format?: "svg", options?: unknown): string;
  }
}
