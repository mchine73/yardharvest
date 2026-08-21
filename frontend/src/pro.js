/**
 * Does this garden have Garden Pro right now?
 *
 * The rule lives on the server (require_garden_pro); this mirrors it so the UI
 * never shows a locked tab the API would happily serve. It was written out
 * longhand in three places and drifted — a garden inside the past_due grace
 * kept dues and messaging and silently lost its photo gallery.
 *
 * `past_due` is included deliberately: the dunning email promises Pro keeps
 * working for seven days while the card is fixed. The server enforces that
 * window; the UI simply does not lock the door early, and anything the server
 * ultimately refuses still returns 403 with an upgrade prompt.
 */
export const PRO_STATUSES = ['trialing', 'active', 'past_due'];

export function gardenHasPro(garden) {
  return PRO_STATUSES.includes(garden?.subscription_status);
}
