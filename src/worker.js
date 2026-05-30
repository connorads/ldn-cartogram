const ORIGIN_PATH_PATTERN = /^\/@-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?\/?$/;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (ORIGIN_PATH_PATTERN.test(url.pathname)) {
      const indexUrl = new URL(url);
      indexUrl.pathname = "/";
      return env.ASSETS.fetch(new Request(indexUrl, request));
    }
    return env.ASSETS.fetch(request);
  },
};
