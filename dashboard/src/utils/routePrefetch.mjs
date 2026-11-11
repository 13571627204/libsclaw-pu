const prefetchedLoaders = new WeakSet();

export function routeTargetFromHref(href, locationLike = window.location) {
  if (!href) return null;

  let url;
  try {
    url = new URL(href, locationLike.href);
  } catch {
    return null;
  }

  if (url.origin !== locationLike.origin || !url.hash.startsWith('#/')) {
    return null;
  }

  return url.hash.slice(1);
}

export async function prefetchRoute(router, target) {
  if (!target) return;

  const resolved = router.resolve(target);
  const pendingLoads = [];

  for (const record of resolved.matched || []) {
    const components = record.components ||
      (record.component ? { default: record.component } : {});

    for (const component of Object.values(components)) {
      if (typeof component !== 'function' || prefetchedLoaders.has(component)) {
        continue;
      }

      prefetchedLoaders.add(component);
      pendingLoads.push(
        Promise.resolve()
          .then(() => component())
          .catch(() => {
            // A failed speculative load must remain retryable during navigation.
            prefetchedLoaders.delete(component);
          }),
      );
    }
  }

  await Promise.all(pendingLoads);
}

/**
 * Warm lazy route chunks when the user signals navigation intent. This keeps
 * normal page splitting while making sidebar and internal-link clicks feel
 * immediate after a short hover, focus, or touch.
 */
export function installRoutePrefetch(
  router,
  { root = document, locationLike = window.location } = {},
) {
  if (navigator.connection?.saveData) {
    return () => undefined;
  }

  const handleIntent = (event) => {
    const anchor = event.target?.closest?.('a[href]');
    if (
      !anchor ||
      anchor.target === '_blank' ||
      anchor.hasAttribute('download') ||
      anchor.dataset.noPrefetch === 'true'
    ) {
      return;
    }

    const target = routeTargetFromHref(anchor.getAttribute('href'), locationLike);
    if (target) {
      void prefetchRoute(router, target);
    }
  };

  root.addEventListener('pointerover', handleIntent, { passive: true });
  root.addEventListener('focusin', handleIntent);
  root.addEventListener('touchstart', handleIntent, { passive: true });

  return () => {
    root.removeEventListener('pointerover', handleIntent);
    root.removeEventListener('focusin', handleIntent);
    root.removeEventListener('touchstart', handleIntent);
  };
}
