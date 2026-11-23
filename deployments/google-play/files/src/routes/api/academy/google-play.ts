import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/api/academy/google-play')({
  server: { handlers: { POST: async ({ request }) => {
    const { playCheckout } = await import('@/lib/mca-play.server');
    return playCheckout(request);
  } } },
});
