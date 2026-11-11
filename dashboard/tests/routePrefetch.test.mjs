import test from 'node:test';
import assert from 'node:assert/strict';

import {
  prefetchRoute,
  routeTargetFromHref,
} from '../src/utils/routePrefetch.mjs';

test('routeTargetFromHref resolves only same-origin hash routes', () => {
  const locationLike = {
    href: 'http://localhost:3007/#/welcome',
    origin: 'http://localhost:3007',
  };

  assert.equal(
    routeTargetFromHref('/#/knowledge-base?tab=wiki', locationLike),
    '/knowledge-base?tab=wiki',
  );
  assert.equal(
    routeTargetFromHref('https://example.com/#/welcome', locationLike),
    null,
  );
  assert.equal(routeTargetFromHref('/assets/app.js', locationLike), null);
});

test('prefetchRoute warms each lazy route component once', async () => {
  let layoutLoads = 0;
  let pageLoads = 0;
  const layout = async () => {
    layoutLoads += 1;
    return { default: {} };
  };
  const page = async () => {
    pageLoads += 1;
    return { default: {} };
  };
  const router = {
    resolve: () => ({
      matched: [
        { components: { default: layout } },
        { components: { default: page } },
      ],
    }),
  };

  await prefetchRoute(router, '/welcome');
  await prefetchRoute(router, '/welcome');

  assert.equal(layoutLoads, 1);
  assert.equal(pageLoads, 1);
});

test('failed speculative loads can be retried', async () => {
  let attempts = 0;
  const flakyPage = async () => {
    attempts += 1;
    if (attempts === 1) throw new Error('temporary failure');
    return { default: {} };
  };
  const router = {
    resolve: () => ({ matched: [{ component: flakyPage }] }),
  };

  await prefetchRoute(router, '/retry');
  await prefetchRoute(router, '/retry');

  assert.equal(attempts, 2);
});
