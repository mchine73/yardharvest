import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { groupsAPI } from '../api';
import { useAuth } from '../AuthContext';

const NEIGHBORHOODS = [
  'Dundee', 'Benson', 'Blackstone', 'Aksarben', 'Midtown',
  'Elkhorn', 'Papillion', 'Ralston', 'Florence', 'Little Italy',
];

export default function GroupsDiscover() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [groups, setGroups] = useState([]);
  const [pagination, setPagination] = useState({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [zipCode, setZipCode] = useState(searchParams.get('zip_code') || (user?.zip_code || ''));
  const [radius, setRadius] = useState(searchParams.get('radius') || '25');

  const page = parseInt(searchParams.get('page') || '1');
  const neighborhood = searchParams.get('neighborhood') || '';
  const activeZip = searchParams.get('zip_code') || '';
  const activeRadius = searchParams.get('radius') || '';

  useEffect(() => {
    setLoading(true);
    const params = { page, search: searchParams.get('search') || '', neighborhood };
    if (activeZip) {
      params.zip_code = activeZip;
      params.radius = activeRadius || 25;
    }
    groupsAPI.browse(params)
      .then(res => {
        setGroups(res.data.groups);
        setPagination(res.data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [page, neighborhood, searchParams.get('search'), activeZip, activeRadius]);

  const handleSearch = (e) => {
    e.preventDefault();
    const p = new URLSearchParams();
    if (search) p.set('search', search);
    if (neighborhood) p.set('neighborhood', neighborhood);
    if (zipCode) p.set('zip_code', zipCode);
    if (zipCode && radius) p.set('radius', radius);
    setSearchParams(p);
  };

  const setNeighborhoodFilter = (n) => {
    const p = new URLSearchParams();
    if (search) p.set('search', search);
    if (n) p.set('neighborhood', n);
    if (zipCode) p.set('zip_code', zipCode);
    if (zipCode && radius) p.set('radius', radius);
    setSearchParams(p);
  };

  const styles = {
    hero: {},
    heroTitle: { fontSize: 32, fontWeight: 700, marginBottom: 8 },
    heroSub: { fontSize: 16, opacity: 0.9, marginBottom: 24 },
    searchRow: {
      display: 'flex',
      gap: 12,
      maxWidth: 600,
      margin: '0 auto',
      flexWrap: 'wrap',
      justifyContent: 'center',
    },
    searchInput: {
      flex: 1,
      minWidth: 200,
      padding: '10px 16px',
      borderRadius: 8,
      border: 'none',
      fontSize: 15,
    },
    searchBtn: {
      padding: '10px 24px',
      borderRadius: 8,
      border: 'none',
      backgroundColor: 'var(--brand-pale)',
      color: 'var(--brand-secondary)',
      fontWeight: 600,
      cursor: 'pointer',
    },
    locationRow: {
      display: 'flex',
      gap: 10,
      maxWidth: 600,
      margin: '12px auto 0',
      justifyContent: 'center',
      alignItems: 'center',
      flexWrap: 'wrap',
    },
    zipInput: {
      width: 120,
      padding: '10px 14px',
      borderRadius: 8,
      border: 'none',
      fontSize: 15,
    },
    radiusSelect: {
      padding: '10px 14px',
      borderRadius: 8,
      border: 'none',
      fontSize: 15,
      backgroundColor: '#fff',
      cursor: 'pointer',
    },
    distanceBadge: {
      display: 'inline-block',
      fontSize: 12,
      fontWeight: 600,
      color: 'var(--brand-secondary)',
      backgroundColor: 'var(--brand-pale)',
      padding: '2px 10px',
      borderRadius: 12,
      marginLeft: 8,
    },
    filterRow: {
      display: 'flex',
      gap: 8,
      flexWrap: 'wrap',
      marginBottom: 24,
      alignItems: 'center',
    },
    filterChip: (active) => ({
      padding: '6px 16px',
      borderRadius: 20,
      border: active ? '2px solid var(--brand-secondary)' : '1px solid #ccc',
      backgroundColor: active ? 'var(--brand-pale)' : '#fff',
      color: active ? 'var(--brand-secondary)' : '#555',
      fontWeight: active ? 600 : 400,
      cursor: 'pointer',
      fontSize: 13,
    }),
    grid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
      gap: 24,
    },
    card: {
      border: '1px solid #e0e0e0',
      borderRadius: 12,
      overflow: 'hidden',
      transition: 'box-shadow 0.2s',
      backgroundColor: '#fff',
    },
    cardCover: {
      height: 140,
      background: 'linear-gradient(135deg, var(--brand-light-green) 0%, var(--brand-accent) 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    },
    cardCoverIcon: { fontSize: 48, color: 'rgba(255,255,255,0.7)' },
    cardBody: { padding: 20 },
    cardName: { fontSize: 18, fontWeight: 700, color: 'var(--brand-primary)', marginBottom: 4 },
    cardNeighborhood: {
      fontSize: 13,
      color: 'var(--brand-accent)',
      fontWeight: 600,
      marginBottom: 8,
      display: 'flex',
      alignItems: 'center',
      gap: 4,
    },
    cardDesc: {
      fontSize: 14,
      color: '#555',
      marginBottom: 12,
      display: '-webkit-box',
      WebkitLineClamp: 2,
      WebkitBoxOrient: 'vertical',
      overflow: 'hidden',
    },
    cardStats: {
      display: 'flex',
      gap: 16,
      fontSize: 13,
      color: '#777',
    },
    createBtn: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      padding: '10px 24px',
      backgroundColor: '#fff',
      color: 'var(--brand-secondary)',
      border: '2px solid var(--brand-secondary)',
      borderRadius: 8,
      fontWeight: 600,
      textDecoration: 'none',
      fontSize: 15,
    },
    topBar: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 16,
    },
  };

  return (
    <>
      <div className="hero-section text-center">
        <h1 style={styles.heroTitle}>
          <i className="bi bi-people me-2"></i>
          Neighborhood Garden Groups
        </h1>
        <p style={styles.heroSub}>
          Connect with gardeners in your Omaha neighborhood. Share tips, trade produce, and grow together.
        </p>
        <form onSubmit={handleSearch} style={styles.searchRow}>
          <input
            type="text"
            style={styles.searchInput}
            placeholder="Search groups..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <button type="submit" style={styles.searchBtn}>
            <i className="bi bi-search me-1"></i> Search
          </button>
        </form>
        <div style={styles.locationRow}>
          <i className="bi bi-geo-alt" style={{ color: '#fff', fontSize: 18 }}></i>
          <input
            type="text"
            style={styles.zipInput}
            placeholder="Zip Code"
            value={zipCode}
            onChange={e => setZipCode(e.target.value)}
            maxLength={10}
          />
          <select
            style={styles.radiusSelect}
            value={radius}
            onChange={e => setRadius(e.target.value)}
          >
            <option value="5">5 miles</option>
            <option value="10">10 miles</option>
            <option value="25">25 miles</option>
            <option value="50">50 miles</option>
          </select>
        </div>
      </div>

      <div style={styles.topBar}>
        <h5 style={{ margin: 0, color: 'var(--brand-primary)' }}>
          {pagination.total || 0} groups found
        </h5>
        {user && (
          <Link to="/groups/create" style={styles.createBtn}>
            <i className="bi bi-plus-circle"></i> Create Group
          </Link>
        )}
      </div>

      <div style={styles.filterRow}>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#555' }}>Filter:</span>
        <button
          style={styles.filterChip(!neighborhood)}
          onClick={() => setNeighborhoodFilter('')}
        >
          All
        </button>
        {NEIGHBORHOODS.map(n => (
          <button
            key={n}
            style={styles.filterChip(neighborhood === n)}
            onClick={() => setNeighborhoodFilter(n)}
          >
            {n}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-5"><div className="spinner-border text-success"></div></div>
      ) : groups.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#888' }}>
          <i className="bi bi-people" style={{ fontSize: 48, display: 'block', marginBottom: 12 }}></i>
          <p>No groups found. Be the first to create one!</p>
          {user && (
            <Link to="/groups/create" className="btn btn-success">Create a Group</Link>
          )}
        </div>
      ) : (
        <div style={styles.grid}>
          {groups.map(g => (
            <Link
              key={g.id}
              to={`/groups/${g.id}`}
              style={{ textDecoration: 'none', color: 'inherit' }}
            >
              <div
                style={styles.card}
                onMouseEnter={e => e.currentTarget.style.boxShadow = '0 4px 20px rgba(22,111,76,0.15)'}
                onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
              >
                <div style={{
                  ...styles.cardCover,
                  ...(g.cover_photo_url ? {
                    backgroundImage: `url(${g.cover_photo_url})`,
                    backgroundSize: 'cover',
                    backgroundPosition: 'center',
                  } : {}),
                }}>
                  {!g.cover_photo_url && (
                    <i className="bi bi-flower2" style={styles.cardCoverIcon}></i>
                  )}
                </div>
                <div style={styles.cardBody}>
                  <div style={styles.cardName}>{g.name}</div>
                  {g.neighborhood && (
                    <div style={styles.cardNeighborhood}>
                      <i className="bi bi-geo-alt-fill"></i> {g.neighborhood}, {g.city}
                    </div>
                  )}
                  <div style={styles.cardDesc}>{g.description}</div>
                  <div style={styles.cardStats}>
                    <span><i className="bi bi-people-fill me-1"></i>{g.member_count} members</span>
                    <span><i className="bi bi-chat-square-text me-1"></i>{g.post_count} posts</span>
                    {g.distance !== undefined && (
                      <span style={styles.distanceBadge}>
                        <i className="bi bi-pin-map me-1"></i>{g.distance} mi away
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {pagination.pages > 1 && (
        <nav className="mt-4">
          <ul className="pagination justify-content-center">
            <li className={`page-item ${!pagination.has_prev ? 'disabled' : ''}`}>
              <button className="page-link" disabled={!pagination.has_prev} onClick={() => {
                const p = new URLSearchParams(searchParams);
                p.set('page', page - 1);
                setSearchParams(p);
              }}>Previous</button>
            </li>
            {Array.from({ length: pagination.pages }, (_, i) => (
              <li key={i} className={`page-item ${page === i + 1 ? 'active' : ''}`}>
                <button className="page-link" onClick={() => {
                  const p = new URLSearchParams(searchParams);
                  p.set('page', i + 1);
                  setSearchParams(p);
                }}>{i + 1}</button>
              </li>
            ))}
            <li className={`page-item ${!pagination.has_next ? 'disabled' : ''}`}>
              <button className="page-link" disabled={!pagination.has_next} onClick={() => {
                const p = new URLSearchParams(searchParams);
                p.set('page', page + 1);
                setSearchParams(p);
              }}>Next</button>
            </li>
          </ul>
        </nav>
      )}
    </>
  );
}
