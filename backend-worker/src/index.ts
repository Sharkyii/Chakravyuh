import { Container, getContainer } from "@cloudflare/containers";

export class FastApiContainer extends Container {
  defaultPort = 8000;
  sleepAfter = "10m";
}

interface Env {
  FASTAPI_CONTAINER: DurableObjectNamespace<FastApiContainer>;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const container = getContainer(env.FASTAPI_CONTAINER);
    return container.fetch(request);
  },
};
