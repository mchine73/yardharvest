import { Fragment, useEffect, useMemo, useState } from 'react';
import { adminAPI } from '../../api';
import { useSubmit } from '../../hooks/useSubmit';
import { toast, confirmDialog } from '../../components/dialog/dialogService';

// Write to the people who run gardens.
//
// Until this, the admin console's "Communication" page only held settings —
// there was no way to actually reach garden managers short of copying emails
// out of the Gardens page. This composes one message to a filtered audience
// and delivers it by email, in-app notification, or both.
//
// Sending is a two-step handshake: preview the audience, then send. The send
// carries the count the preview showed, and the server refuses it if the
// audience has changed since — so nobody receives a message the admin did not
// see would reach them.

const CARD = { border: 'none', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' };
const ROLE_OPTIONS = [
  { value: 'owners', label: 'Garden owners only' },
  { value: 'owners_and_co', label: 'Owners and co-organizers' },
  { value: 'all_staff', label: 'All garden staff (incl. treasurers, volunteer leads)' },
];
const PLAN_LABELS = { active: 'Garden Pro', trialing: 'On trial', none: 'Free', expired: 'Lapsed' };
const MAX_BODY = 5000;

export default function ManagerMessaging() {
  const [options, setOptions] = useState(null);
  const [roles, setRoles] = useState('owners_and_co');
  const [plans, setPlans] = useState([]);
  const [states, setStates] = useState([]);
  const [gardenIds, setGardenIds] = useState([]);
  const [activeOnly, setActiveOnly] = useState(true);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [channels, setChannels] = useState(['email', 'inapp']);
  const [preview, setPreview] = useState(null);
  const [history, setHistory] = useState([]);
  const [openId, setOpenId] = useState(null);
  const { pending: previewing, run: runPreview } = useSubmit();
  const { pending: sending, run: runSend } = useSubmit();

  const audience = useMemo(() => ({
    roles, plans, states, garden_ids: gardenIds, active_only: activeOnly,
  }), [roles, plans, states, gardenIds, activeOnly]);

  // Any change to who it reaches invalidates the preview: the send must be
  // based on a preview of THIS audience, not the last one.
  useEffect(() => { setPreview(null); }, [audience]);

  const loadHistory = () => adminAPI.managerBroadcasts()
    .then((r) => setHistory(r.data.broadcasts || [])).catch(() => {});

  useEffect(() => {
    adminAPI.managerAudienceOptions().then((r) => setOptions(r.data)).catch(() => {});
    loadHistory();
  }, []);

  const toggle = (list, setList, v) => setList(
    list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  const doPreview = () => runPreview(
    () => adminAPI.managerBroadcastPreview({ audience }),
    { error: 'Could not preview that audience.' },
  ).then(({ ok, data }) => { if (ok) setPreview(data.data); });

  const canSend = preview && preview.count > 0 && subject.trim() && body.trim()
    && channels.length > 0 && body.length <= MAX_BODY;

  const doSend = async () => {
    const via = channels.map((c) => (c === 'email' ? 'email' : 'in-app notification')).join(' and ');
    const ok = await confirmDialog(
      `Send "${subject.trim()}" to ${preview.count} garden manager${preview.count === 1 ? '' : 's'} by ${via}?`
      + (channels.includes('email') && preview.suppressed
        ? ` ${preview.suppressed} have unsubscribed or bounced and will not be emailed.` : ''),
      { title: 'Send to garden managers', confirmText: 'Send' },
    );
    if (!ok) return;
    const res = await runSend(() => adminAPI.managerBroadcast({
      subject: subject.trim(), body: body.trim(), channels, audience,
      expected_count: preview.count,
    }), { error: 'The message was not sent.' });
    if (!res.ok) {
      // 409: the audience moved between preview and send. Make them look again.
      if (res.error?.response?.status === 409) setPreview(null);
      return;
    }
    const b = res.data.data.broadcast;
    toast(`Sent to ${b.recipient_count}: ${b.emailed} emailed, ${b.notified} notified`
      + (b.email_failed ? `, ${b.email_failed} failed` : ''), { type: b.email_failed ? 'warning' : 'success' });
    setSubject('');
    setBody('');
    setPreview(null);
    loadHistory();
  };

  return (
    <>
      <div className="card mb-4" style={CARD}>
        <div className="card-body">
          <h5 className="fw-bold mb-1"><i className="bi bi-megaphone me-2" />Message garden managers</h5>
          <p className="text-muted small mb-4">
            One message to the people who run gardens on YardHarvest. Each person receives it once,
            even if they manage several gardens, and the email names the gardens they manage.
          </p>

          <div className="row g-4">
            <div className="col-lg-5">
              <h6 className="fw-semibold">1. Who should get it?</h6>

              <label className="form-label small fw-semibold mt-2" htmlFor="mm-roles">Managers</label>
              <select id="mm-roles" className="form-select form-select-sm" value={roles}
                      onChange={(e) => setRoles(e.target.value)}>
                {ROLE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>

              <div className="form-label small fw-semibold mt-3 mb-1">Plan</div>
              <div className="d-flex flex-wrap gap-2">
                {Object.entries(PLAN_LABELS).map(([k, label]) => (
                  <button key={k} type="button"
                          className={`btn btn-sm rounded-pill ${plans.includes(k) ? 'btn-dark' : 'btn-outline-secondary'}`}
                          onClick={() => toggle(plans, setPlans, k)}>
                    {label}
                    {options?.plan_counts?.[k] != null && (
                      <span className="ms-1 opacity-75">({options.plan_counts[k]})</span>
                    )}
                  </button>
                ))}
              </div>
              <div className="form-text">None selected means every plan.</div>

              {options?.states?.length > 0 && (
                <>
                  <div className="form-label small fw-semibold mt-3 mb-1">State</div>
                  <div className="d-flex flex-wrap gap-1">
                    {options.states.map((s) => (
                      <button key={s} type="button"
                              className={`btn btn-sm ${states.includes(s) ? 'btn-dark' : 'btn-outline-secondary'}`}
                              onClick={() => toggle(states, setStates, s)}>
                        {s}
                      </button>
                    ))}
                  </div>
                  <div className="form-text">None selected means everywhere.</div>
                </>
              )}

              {options?.gardens?.length > 0 && (
                <>
                  <label className="form-label small fw-semibold mt-3" htmlFor="mm-gardens">
                    Specific gardens <span className="fw-normal text-muted">(optional)</span>
                  </label>
                  <select id="mm-gardens" multiple className="form-select form-select-sm" size={5}
                          value={gardenIds.map(String)}
                          onChange={(e) => setGardenIds([...e.target.selectedOptions].map((o) => Number(o.value)))}>
                    {options.gardens.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}{g.state ? ` · ${g.state}` : ''} · {PLAN_LABELS[g.plan] || g.plan}
                      </option>
                    ))}
                  </select>
                  <div className="form-text">Ctrl/Cmd-click to choose several. Empty means all that match.</div>
                </>
              )}

              <div className="form-check mt-3">
                <input id="mm-active" className="form-check-input" type="checkbox" checked={activeOnly}
                       onChange={(e) => setActiveOnly(e.target.checked)} />
                <label className="form-check-label small" htmlFor="mm-active">
                  Only gardens that are active (not deactivated)
                </label>
              </div>

              <button type="button" className="btn btn-outline-dark btn-sm mt-3" onClick={doPreview}
                      disabled={previewing}>
                <i className="bi bi-people me-1" />{previewing ? 'Checking…' : 'Preview recipients'}
              </button>

              {preview && (
                <div className="mt-3 p-3 rounded" style={{ background: 'var(--yh-surface-2, #f6f7f5)' }}>
                  <div className="fw-semibold">
                    {preview.count} {preview.count === 1 ? 'person' : 'people'}
                  </div>
                  {preview.suppressed > 0 && (
                    <div className="small text-warning-emphasis">
                      {preview.suppressed} unsubscribed or bounced — they get the in-app notice only.
                    </div>
                  )}
                  {channels.includes('email') && (
                    <div className="small text-muted">
                      Email cost ≈ ${Number(preview.est_email_cost_usd).toFixed(4)}
                    </div>
                  )}
                  <ul className="list-unstyled small mt-2 mb-0" style={{ maxHeight: 220, overflowY: 'auto' }}>
                    {preview.recipients.map((r) => (
                      <li key={r.id} className="py-1 border-bottom">
                        <span className={r.suppressed ? 'text-decoration-line-through text-muted' : ''}>
                          {r.name}
                        </span>
                        <span className="text-muted"> · {r.email}</span>
                        <div className="text-muted" style={{ fontSize: '0.75rem' }}>{r.gardens.join(', ')}</div>
                      </li>
                    ))}
                  </ul>
                  {preview.truncated && <div className="small text-muted mt-1">Showing the first 200.</div>}
                  {preview.count === 0 && <div className="small text-muted">That audience matches nobody.</div>}
                </div>
              )}
            </div>

            <div className="col-lg-7">
              <h6 className="fw-semibold">2. What should it say?</h6>
              <label className="form-label small fw-semibold mt-2" htmlFor="mm-subject">Subject</label>
              <input id="mm-subject" className="form-control" maxLength={200} value={subject}
                     onChange={(e) => setSubject(e.target.value)} placeholder="e.g. New: online dues for the 2027 season" />

              <label className="form-label small fw-semibold mt-3" htmlFor="mm-body">Message</label>
              <textarea id="mm-body" className="form-control" rows={10} value={body}
                        onChange={(e) => setBody(e.target.value)}
                        placeholder={'Write plainly. A blank line starts a new paragraph.\n\nEach email opens with "Hi <their name>," and closes by naming the gardens they manage — you don\'t need to add either.'} />
              <div className={`form-text ${body.length > MAX_BODY ? 'text-danger' : ''}`}>
                {body.length.toLocaleString()} / {MAX_BODY.toLocaleString()}
              </div>

              <div className="form-label small fw-semibold mt-3 mb-1">Deliver by</div>
              {[['email', 'Email'], ['inapp', 'In-app notification (and phone push)']].map(([k, label]) => (
                <div className="form-check form-check-inline" key={k}>
                  <input id={`mm-ch-${k}`} className="form-check-input" type="checkbox"
                         checked={channels.includes(k)} onChange={() => toggle(channels, setChannels, k)} />
                  <label className="form-check-label small" htmlFor={`mm-ch-${k}`}>{label}</label>
                </div>
              ))}

              <div className="mt-4 d-flex align-items-center gap-3 flex-wrap">
                <button type="button" className="btn btn-dark" onClick={doSend} disabled={!canSend || sending}>
                  <i className="bi bi-send me-1" />
                  {sending ? 'Sending…' : preview ? `Send to ${preview.count}` : 'Send'}
                </button>
                {!preview && <span className="small text-muted">Preview the recipients first.</span>}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="card mb-4" style={CARD}>
        <div className="card-body">
          <h6 className="fw-bold mb-3"><i className="bi bi-clock-history me-2" />Sent to managers</h6>
          {history.length === 0 ? (
            <p className="text-muted mb-0">Nothing sent yet.</p>
          ) : (
            <div className="table-responsive">
              <table className="table table-sm align-middle mb-0">
                <thead>
                  <tr>
                    <th>When</th><th>Subject</th><th className="text-end">Reached</th>
                    <th className="text-end">Emailed</th><th className="text-end">Failed</th>
                    <th className="text-end">Skipped</th><th className="text-end">In-app</th><th />
                  </tr>
                </thead>
                <tbody>
                  {history.map((b) => (
                    // The key belongs on the fragment: it is the list item.
                    <Fragment key={b.id}>
                      <tr>
                        <td className="small text-nowrap">{b.created_at ? new Date(b.created_at).toLocaleString() : ''}</td>
                        <td>{b.subject}<div className="small text-muted">{b.sender}</div></td>
                        <td className="text-end">{b.recipient_count}</td>
                        <td className="text-end">{b.emailed}</td>
                        <td className={`text-end ${b.email_failed ? 'text-danger fw-semibold' : ''}`}>{b.email_failed}</td>
                        <td className="text-end">{b.suppressed}</td>
                        <td className="text-end">{b.notified}</td>
                        <td className="text-end">
                          <button type="button" className="btn btn-link btn-sm p-0"
                                  onClick={() => setOpenId(openId === b.id ? null : b.id)}>
                            {openId === b.id ? 'Hide' : 'View'}
                          </button>
                        </td>
                      </tr>
                      {openId === b.id && (
                        <tr>
                          <td colSpan={8} className="small" style={{ whiteSpace: 'pre-wrap', background: '#fafafa' }}>
                            {b.body}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
