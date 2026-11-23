export const PLAY_PACKAGE = 'eu.markacentrumacademy.app';
export const PLAY_COURSES: Record<string, string> = {
  '11111111-1111-4111-8111-111111111111': 'mca_bitumen_basic_lifetime',
  'f166433e-5157-4341-9a38-800c62795ebd': 'mca_bitumen_renovation_lifetime',
};

export class PlayError extends Error {
  readonly code: string;
  readonly status: number;
  constructor(code: string, status = 400) { super(code); this.code = code; this.status = status; }
}

export interface VerifiedPurchase {
  state: 'pending' | 'purchased' | 'cancelled';
  orderId: string | null;
  paidAt: string | null;
  acknowledged: boolean;
  test: boolean;
}

/** Only authenticated Publisher API responses may be passed to this function. */
export function validatePurchase(value: unknown, sku: string, accountId: string): VerifiedPurchase {
  if (!value || typeof value !== 'object') throw new PlayError('invalid_purchase');
  const p = value as Record<string, any>;
  if (!Object.values(PLAY_COURSES).includes(sku) || !/^[a-f0-9]{64}$/.test(accountId) ||
      p.obfuscatedExternalAccountId !== accountId) throw new PlayError('account_mismatch', 409);
  if (!Array.isArray(p.productLineItem) || p.productLineItem.length !== 1 ||
      p.productLineItem[0]?.productId !== sku) throw new PlayError('product_mismatch', 409);
  const offer = p.productLineItem[0].productOfferDetails;
  if (!offer || offer.quantity !== 1 || offer.rentOfferDetails || offer.preorderOfferDetails ||
      (offer.purchaseOptionId && offer.purchaseOptionId !== 'lifetime') ||
      offer.consumptionState !== 'CONSUMPTION_STATE_YET_TO_BE_CONSUMED') {
    throw new PlayError('unsupported_purchase', 409);
  }
  const states: Record<string, VerifiedPurchase['state']> = {
    PURCHASED: 'purchased', PENDING: 'pending', CANCELLED: 'cancelled',
  };
  let state = states[p.purchaseStateContext?.purchaseState];
  if (!state) throw new PlayError('invalid_purchase_state', 409);
  if (state === 'purchased' && offer.refundableQuantity === 0) state = 'cancelled';
  if (state === 'purchased' && (!Number.isFinite(Date.parse(p.purchaseCompletionTime)) ||
      Date.parse(p.purchaseCompletionTime) > Date.now() + 300000)) throw new PlayError('invalid_purchase_time', 409);
  if (!['ACKNOWLEDGEMENT_STATE_PENDING', 'ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED'].includes(p.acknowledgementState)) {
    throw new PlayError('invalid_acknowledgement', 409);
  }
  return {
    state, orderId: typeof p.orderId === 'string' && p.orderId.length <= 256 ? p.orderId : null,
    paidAt: Number.isFinite(Date.parse(p.purchaseCompletionTime)) ? new Date(p.purchaseCompletionTime).toISOString() : null,
    acknowledged: p.acknowledgementState === 'ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED',
    test: p.testPurchaseContext?.fopType === 'TEST',
  };
}
