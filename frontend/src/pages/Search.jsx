import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { listingsAPI, IMAGE_BASE } from '../api';
import ListingCard from '../components/ListingCard';
import { trackEvent } from '../hooks/useTracking';

const SORT_OPTIONS = [
  { value: 'relevance', label: 'Most Relevant', icon: 'bi-sort-down' },
  { value: 'price_asc', label: 'Price: Low to High', icon: 'bi-sort-numeric-down' },
  { value: 'price_desc', label: 'Price: High to Low', icon: 'bi-sort-numeric-up' },
  { value: 'distance', label: 'Nearest First', icon: 'bi-geo-alt' },
  { value: 'newest', label: 'Newest First', icon: 'bi-clock' },
];

const DEFAULT_FORM = {
  keyword: '',
  vegetable_type: '',
  location: '',
  radius: 10,
  min_price: '',
  max_price: '',
  delivery_only: false,
};

export default function Search() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [categories, setCategories] = useState([]);
  const [results, setResults] = useState([]);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [sortBy, setSortBy] = useState('relevance');
  const [viewMode, setViewMode] = useState('grid');

  // Initialize form from URL params
  const [form, setForm] = useState(() => {
    const fromURL = {};
    for (const key of Object.keys(DEFAULT_FORM)) {
      const val = searchParams.get(key);
      if (val !== null) {
        if (key === 'delivery_only') fromURL[key] = val === 'true';
        else if (key === 'radius') fromURL[key] = parseInt(val, 10) || 10;
        else fromURL[key] = val;
      }
    }
    return { ...DEFAULT_FORM, ...fromURL };
  });

  // Load categories on mount
  useEffect(() => {
    listingsAPI.categories().then(res => setCategories(res.data.categories)).catch(() => {});
  }, []);

  // Auto-search if URL has params on mount
  useEffect(() => {
    const hasParams = Array.from(searchParams.entries()).some(([k]) => Object.keys(DEFAULT_FORM).includes(k));
    if (hasParams) {
      performSearch(form);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const performSearch = useCallback((searchForm) => {
    setLoading(true);
    setSearched(true);

    const params = {};
    if (searchForm.keyword) params.keyword = searchForm.keyword;
    if (searchForm.vegetable_type) params.vegetable_type = searchForm.vegetable_type;
    if (searchForm.location) params.location = searchForm.location;
    if (searchForm.radius) params.radius = searchForm.radius;
    if (searchForm.min_price) params.min_price = searchForm.min_price;
    if (searchForm.max_price) params.max_price = searchForm.max_price;
    if (searchForm.delivery_only) params.delivery_only = true;

    listingsAPI.search(params).then(res => {
      const listings = res.data.listings || [];
      setResults(listings);
      trackEvent('search', { query: searchForm.keyword || '', result_count: listings.length });
      setLoading(false);
    }).catch(() => {
      setResults([]);
      setLoading(false);
    });
  }, []);

  const syncURL = useCallback((formData) => {
    const params = {};
    for (const [key, val] of Object.entries(formData)) {
      if (val !== '' && val !== false && val !== DEFAULT_FORM[key]) {
        params[key] = String(val);
      }
    }
    setSearchParams(params, { replace: true });
  }, [setSearchParams]);

  const handleSearch = (e) => {
    e.preventDefault();
    syncURL(form);
    performSearch(form);
  };

  const handleQuickSearch = (keyword) => {
    const newForm = { ...DEFAULT_FORM, keyword };
    setForm(newForm);
    syncURL(newForm);
    performSearch(newForm);
  };

  const handleClearAll = () => {
    setForm({ ...DEFAULT_FORM });
    setSearchParams({}, { replace: true });
    setResults([]);
    setSearched(false);
    setSortBy('relevance');
  };

  const removeFilter = (key) => {
    const newForm = { ...form, [key]: DEFAULT_FORM[key] };
    setForm(newForm);
    syncURL(newForm);
    performSearch(newForm);
  };

  // Compute active filters for chip display
  const activeFilters = useMemo(() => {
    const chips = [];
    if (form.keyword) chips.push({ key: 'keyword', label: `"${form.keyword}"`, icon: 'bi-search' });
    if (form.vegetable_type) {
      const cat = categories.find(c => c.value === form.vegetable_type);
      chips.push({ key: 'vegetable_type', label: cat ? cat.label : form.vegetable_type, icon: 'bi-tag' });
    }
    if (form.location) chips.push({ key: 'location', label: `Near ${form.location}`, icon: 'bi-geo-alt' });
    if (form.radius !== DEFAULT_FORM.radius) chips.push({ key: 'radius', label: `${form.radius} mi radius`, icon: 'bi-bullseye' });
    if (form.min_price) chips.push({ key: 'min_price', label: `Min $${form.min_price}`, icon: 'bi-currency-dollar' });
    if (form.max_price) chips.push({ key: 'max_price', label: `Max $${form.max_price}`, icon: 'bi-currency-dollar' });
    if (form.delivery_only) chips.push({ key: 'delivery_only', label: 'Delivery Only', icon: 'bi-truck' });
    return chips;
  }, [form, categories]);

  // Client-side sort (API may not support all sorts)
  const sortedResults = useMemo(() => {
    const sorted = [...results];
    switch (sortBy) {
      case 'price_asc':
        sorted.sort((a, b) => (a.effective_price || a.price || 0) - (b.effective_price || b.price || 0));
        break;
      case 'price_desc':
        sorted.sort((a, b) => (b.effective_price || b.price || 0) - (a.effective_price || a.price || 0));
        break;
      case 'distance':
        sorted.sort((a, b) => (a.distance ?? 9999) - (b.distance ?? 9999));
        break;
      case 'newest':
        sorted.sort((a, b) => (b.id || 0) - (a.id || 0));
        break;
      default:
        break;
    }
    return sorted;
  }, [results, sortBy]);

  const quickSearches = [
    { label: 'Tomatoes', icon: 'bi-flower2' },
    { label: 'Peppers', icon: 'bi-fire' },
    { label: 'Herbs', icon: 'bi-leaf' },
    { label: 'Eggs', icon: 'bi-egg' },
    { label: 'Squash', icon: 'bi-circle' },
    { label: 'Berries', icon: 'bi-heart-fill' },
  ];

  return (
    <div>
      {/* Search Hero */}
      <div
        className="hero-section text-center position-relative overflow-hidden"
      >
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
          background: 'url("data:image/svg+xml,%3Csvg width=\'40\' height=\'40\' viewBox=\'0 0 40 40\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cg fill=\'%23ffffff\' fill-opacity=\'0.04\'%3E%3Cpath d=\'M20 20c0-5.5-4.5-10-10-10S0 14.5 0 20s4.5 10 10 10 10-4.5 10-10zm20 0c0-5.5-4.5-10-10-10s-10 4.5-10 10 4.5 10 10 10 10-4.5 10-10z\'/%3E%3C/g%3E%3C/svg%3E")',
        }} />
        <div className="position-relative">
          <h1 className="display-5 fw-bold mb-2">
            <i className="bi bi-search me-3"></i>Find Fresh Local Produce
          </h1>
          <p className="lead mb-4" style={{ opacity: 0.9, maxWidth: '550px', margin: '0 auto' }}>
            Search gardens near you for the freshest fruits, vegetables, herbs, and more.
          </p>

          {/* Main search bar */}
          <form onSubmit={handleSearch} className="d-flex justify-content-center">
            <div className="input-group" style={{ maxWidth: '650px' }}>
              <span className="input-group-text bg-white border-0" style={{ borderRadius: '50px 0 0 50px', paddingLeft: '1.2rem' }}>
                <i className="bi bi-search text-success"></i>
              </span>
              <input
                type="text"
                className="form-control form-control-lg border-0"
                placeholder="Search for tomatoes, peppers, herbs..."
                value={form.keyword}
                onChange={e => setForm({ ...form, keyword: e.target.value })}
                style={{ boxShadow: 'none' }}
              />
              <button
                type="submit"
                className="btn btn-warning btn-lg fw-semibold px-4"
                style={{ borderRadius: '0 50px 50px 0' }}
              >
                Search
              </button>
            </div>
          </form>

          {/* Quick search chips */}
          <div className="d-flex justify-content-center flex-wrap gap-2 mt-3">
            {quickSearches.map(qs => (
              <button
                key={qs.label}
                type="button"
                className="btn btn-sm btn-outline-light rounded-pill px-3"
                onClick={() => handleQuickSearch(qs.label)}
                style={{ opacity: 0.9 }}
              >
                <i className={`bi ${qs.icon} me-1`}></i>{qs.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Advanced Filters Toggle */}
      <div className="d-flex justify-content-between align-items-center mb-3">
        <button
          type="button"
          className="btn btn-outline-success"
          onClick={() => setFiltersOpen(!filtersOpen)}
        >
          <i className={`bi ${filtersOpen ? 'bi-funnel-fill' : 'bi-funnel'} me-2`}></i>
          {filtersOpen ? 'Hide Filters' : 'Advanced Filters'}
          {activeFilters.length > 0 && (
            <span className="badge bg-success ms-2">{activeFilters.length}</span>
          )}
        </button>

        {activeFilters.length > 0 && (
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary"
            onClick={handleClearAll}
          >
            <i className="bi bi-x-circle me-1"></i>Clear All
          </button>
        )}
      </div>

      {/* Advanced Filters Panel */}
      {filtersOpen && (
        <div className="card border-0 shadow-sm mb-4" style={{ borderTop: '3px solid var(--brand-secondary)' }}>
          <div className="card-body p-4">
            <form onSubmit={handleSearch}>
              <div className="row g-3">
                {/* Keyword */}
                <div className="col-md-6 col-lg-4">
                  <label className="form-label fw-semibold small text-muted">
                    <i className="bi bi-search me-1"></i>Keyword
                  </label>
                  <input
                    className="form-control"
                    placeholder="e.g. heirloom tomatoes"
                    value={form.keyword}
                    onChange={e => setForm({ ...form, keyword: e.target.value })}
                  />
                </div>

                {/* Category */}
                <div className="col-md-6 col-lg-4">
                  <label className="form-label fw-semibold small text-muted">
                    <i className="bi bi-tag me-1"></i>Category
                  </label>
                  <select
                    className="form-select"
                    value={form.vegetable_type}
                    onChange={e => setForm({ ...form, vegetable_type: e.target.value })}
                  >
                    <option value="">All Categories</option>
                    {categories.map(c => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </select>
                </div>

                {/* Location */}
                <div className="col-md-6 col-lg-4">
                  <label className="form-label fw-semibold small text-muted">
                    <i className="bi bi-geo-alt me-1"></i>Location
                  </label>
                  <input
                    className="form-control"
                    placeholder="City, ZIP, or neighborhood"
                    value={form.location}
                    onChange={e => setForm({ ...form, location: e.target.value })}
                  />
                </div>

                {/* Radius Slider */}
                <div className="col-md-6 col-lg-4">
                  <label className="form-label fw-semibold small text-muted">
                    <i className="bi bi-bullseye me-1"></i>Radius: {form.radius} miles
                  </label>
                  <input
                    type="range"
                    className="form-range"
                    min="1"
                    max="50"
                    value={form.radius}
                    onChange={e => setForm({ ...form, radius: parseInt(e.target.value, 10) })}
                    style={{ accentColor: 'var(--brand-secondary)' }}
                  />
                  <div className="d-flex justify-content-between">
                    <small className="text-muted">1 mi</small>
                    <small className="text-muted">25 mi</small>
                    <small className="text-muted">50 mi</small>
                  </div>
                </div>

                {/* Price Range */}
                <div className="col-md-6 col-lg-4">
                  <label className="form-label fw-semibold small text-muted">
                    <i className="bi bi-currency-dollar me-1"></i>Price Range
                  </label>
                  <div className="input-group">
                    <span className="input-group-text bg-light">$</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      className="form-control"
                      placeholder="Min"
                      value={form.min_price}
                      onChange={e => setForm({ ...form, min_price: e.target.value })}
                    />
                    <span className="input-group-text bg-light">to</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      className="form-control"
                      placeholder="Max"
                      value={form.max_price}
                      onChange={e => setForm({ ...form, max_price: e.target.value })}
                    />
                  </div>
                </div>

                {/* Toggles */}
                <div className="col-md-6 col-lg-4 d-flex align-items-end">
                  <div className="d-flex flex-column gap-2 w-100">
                    <div className="form-check form-switch">
                      <input
                        className="form-check-input"
                        type="checkbox"
                        id="deliveryToggle"
                        checked={form.delivery_only}
                        onChange={e => setForm({ ...form, delivery_only: e.target.checked })}
                        style={{ width: '2.5em', height: '1.25em' }}
                      />
                      <label className="form-check-label fw-semibold" htmlFor="deliveryToggle">
                        <i className="bi bi-truck me-1 text-success"></i>Delivery Only
                      </label>
                    </div>
                  </div>
                </div>

                {/* Search Button */}
                <div className="col-12">
                  <hr className="my-2" />
                  <div className="d-flex gap-2">
                    <button type="submit" className="btn btn-success px-4">
                      <i className="bi bi-search me-2"></i>Search
                    </button>
                    <button
                      type="button"
                      className="btn btn-outline-secondary"
                      onClick={() => {
                        setForm({ ...DEFAULT_FORM });
                        setSearchParams({}, { replace: true });
                      }}
                    >
                      <i className="bi bi-arrow-counterclockwise me-1"></i>Reset Filters
                    </button>
                  </div>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Active Filter Chips */}
      {activeFilters.length > 0 && (
        <div className="d-flex flex-wrap gap-2 mb-3">
          {activeFilters.map(chip => (
            <span
              key={chip.key}
              className="badge bg-light text-dark border d-inline-flex align-items-center px-3 py-2"
              style={{ fontSize: '0.85rem' }}
            >
              <i className={`bi ${chip.icon} text-success me-1`}></i>
              {chip.label}
              <button
                type="button"
                className="btn-close btn-close-sm ms-2"
                style={{ fontSize: '0.6rem' }}
                onClick={() => removeFilter(chip.key)}
                aria-label={`Remove ${chip.label} filter`}
              ></button>
            </span>
          ))}
        </div>
      )}

      {/* Results Header */}
      {searched && !loading && (
        <div className="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-3 p-3 rounded-3" style={{ background: '#f8f9fa' }}>
          <div>
            <span className="fw-bold text-success fs-5">{sortedResults.length}</span>
            <span className="text-muted ms-1">
              {sortedResults.length === 1 ? 'result' : 'results'} found
            </span>
          </div>
          <div className="d-flex align-items-center gap-3">
            {/* Sort Dropdown */}
            <div className="d-flex align-items-center gap-2">
              <label className="text-muted small mb-0 d-none d-md-inline">Sort by:</label>
              <select
                className="form-select form-select-sm"
                style={{ width: 'auto' }}
                value={sortBy}
                onChange={e => setSortBy(e.target.value)}
              >
                {SORT_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>

            {/* View Toggle */}
            <div className="btn-group btn-group-sm" role="group">
              <button
                type="button"
                className={`btn ${viewMode === 'grid' ? 'btn-success' : 'btn-outline-success'}`}
                onClick={() => setViewMode('grid')}
                title="Grid view"
              >
                <i className="bi bi-grid-3x3-gap-fill"></i>
              </button>
              <button
                type="button"
                className={`btn ${viewMode === 'list' ? 'btn-success' : 'btn-outline-success'}`}
                onClick={() => setViewMode('list')}
                title="List view"
              >
                <i className="bi bi-list-ul"></i>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="text-center py-5">
          <div className="spinner-border text-success mb-3" style={{ width: '3rem', height: '3rem' }}></div>
          <p className="text-muted">Searching gardens near you...</p>
        </div>
      )}

      {/* Results Grid */}
      {!loading && searched && sortedResults.length > 0 && (
        <div className="row">
          {viewMode === 'grid' ? (
            sortedResults.map(listing => (
              <ListingCard key={listing.id} listing={listing} />
            ))
          ) : (
            sortedResults.map(listing => (
              <div className="col-12 mb-3" key={listing.id}>
                <div className="card shadow-sm listing-card">
                  <div className="row g-0">
                    <div className="col-md-3">
                      <img
                        src={
                          listing.image_filename
                            ? `${IMAGE_BASE}${listing.image_filename}`
                            : listing.image_url || '/placeholder-produce.svg'
                        }
                        className="img-fluid rounded-start"
                        alt={listing.title}
                        style={{ height: '100%', objectFit: 'cover', minHeight: '150px' }}
                      />
                    </div>
                    <div className="col-md-9">
                      <div className="card-body d-flex flex-column h-100">
                        <div className="d-flex justify-content-between align-items-start">
                          <div>
                            <h5 className="card-title fw-bold mb-1">{listing.title}</h5>
                            <p className="text-muted small mb-2">
                              <i className="bi bi-person me-1"></i>{listing.seller_name}
                              {listing.distance !== undefined && (
                                <span className="ms-3">
                                  <i className="bi bi-geo-alt me-1"></i>{listing.distance} mi away
                                </span>
                              )}
                            </p>
                          </div>
                          <div className="text-end">
                            <span className="fw-bold text-success fs-4">
                              ${listing.effective_price?.toFixed(2) || listing.price?.toFixed(2)}
                            </span>
                            <small className="text-muted d-block">/{listing.unit}</small>
                          </div>
                        </div>
                        {listing.description && (
                          <p className="text-muted small mb-2 flex-grow-1">
                            {listing.description.length > 150
                              ? listing.description.substring(0, 150) + '...'
                              : listing.description}
                          </p>
                        )}
                        <div className="d-flex justify-content-between align-items-center mt-auto">
                          <div className="d-flex gap-2">
                            {listing.effective_price && listing.base_price && listing.effective_price > listing.base_price + 0.01 && (
                              <span className="badge bg-warning text-dark">
                                <i className="bi bi-graph-up me-1"></i>High demand
                              </span>
                            )}
                          </div>
                          <Link to={`/listings/${listing.id}`} className="btn btn-sm btn-outline-success">
                            View Details <i className="bi bi-arrow-right ms-1"></i>
                          </Link>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* No Results State */}
      {!loading && searched && sortedResults.length === 0 && (
        <div className="text-center py-5">
          <div
            className="rounded-circle d-inline-flex align-items-center justify-content-center mb-4"
            style={{ width: '100px', height: '100px', background: '#f0faf0' }}
          >
            <i className="bi bi-search" style={{ fontSize: '2.5rem', color: '#a5d6a7' }}></i>
          </div>
          <h4 className="fw-bold mb-2">No results found</h4>
          <p className="text-muted mb-4" style={{ maxWidth: '450px', margin: '0 auto' }}>
            We couldn&apos;t find any listings matching your search. Try adjusting your filters or searching for something different.
          </p>
          <div className="d-flex flex-column align-items-center gap-3">
            <div>
              <h6 className="text-muted mb-2">Suggestions:</h6>
              <ul className="list-unstyled text-muted text-start">
                <li className="mb-1"><i className="bi bi-lightbulb text-warning me-2"></i>Try broader search terms</li>
                <li className="mb-1"><i className="bi bi-lightbulb text-warning me-2"></i>Increase your search radius</li>
                <li className="mb-1"><i className="bi bi-lightbulb text-warning me-2"></i>Remove some filters</li>
                <li className="mb-1"><i className="bi bi-lightbulb text-warning me-2"></i>Check back later &mdash; new listings are added daily</li>
              </ul>
            </div>
            <div className="d-flex gap-2">
              <button className="btn btn-success" onClick={handleClearAll}>
                <i className="bi bi-arrow-counterclockwise me-1"></i>Clear All Filters
              </button>
              <Link to="/browse" className="btn btn-outline-success">
                <i className="bi bi-grid me-1"></i>Browse All Listings
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Pre-search state */}
      {!loading && !searched && (
        <div className="text-center py-5">
          <div
            className="rounded-circle d-inline-flex align-items-center justify-content-center mb-4"
            style={{ width: '120px', height: '120px', background: 'linear-gradient(135deg, #edf7cf, #e3ff8f)' }}
          >
            <i className="bi bi-flower1" style={{ fontSize: '3rem', color: '#22242a' }}></i>
          </div>
          <h3 className="fw-bold mb-2">What are you looking for?</h3>
          <p className="text-muted mb-4" style={{ maxWidth: '500px', margin: '0 auto' }}>
            Use the search bar above or click a quick search to find fresh, local produce
            from gardens in your neighborhood.
          </p>
          <div className="row g-3 justify-content-center" style={{ maxWidth: '800px', margin: '0 auto' }}>
            {[
              { label: 'Tomatoes', icon: 'bi-flower2', color: '#e53935' },
              { label: 'Peppers', icon: 'bi-fire', color: '#ff9800' },
              { label: 'Herbs', icon: 'bi-leaf', color: '#43a047' },
              { label: 'Eggs', icon: 'bi-egg', color: '#795548' },
              { label: 'Squash', icon: 'bi-circle', color: '#ff7043' },
              { label: 'Cucumbers', icon: 'bi-flower3', color: '#26a69a' },
              { label: 'Berries', icon: 'bi-heart-fill', color: '#c62828' },
              { label: 'Corn', icon: 'bi-sun', color: '#f9a825' },
            ].map(item => (
              <div className="col-6 col-md-3" key={item.label}>
                <button
                  type="button"
                  className="w-100 p-3 d-flex flex-column align-items-center"
                  style={{
                    borderRadius: '12px',
                    transition: 'all 0.2s',
                    border: 'none',
                    backgroundColor: '#f8f9fa',
                    color: '#555',
                    cursor: 'pointer',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                  }}
                  onClick={() => handleQuickSearch(item.label)}
                  onMouseEnter={e => {
                    e.currentTarget.style.backgroundColor = '#e8f5e9';
                    e.currentTarget.style.color = item.color;
                    e.currentTarget.style.boxShadow = '0 4px 12px rgba(22,111,76,0.15)';
                    e.currentTarget.style.transform = 'translateY(-2px)';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.backgroundColor = '#f8f9fa';
                    e.currentTarget.style.color = '#555';
                    e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.06)';
                    e.currentTarget.style.transform = '';
                  }}
                >
                  <i className={`bi ${item.icon} mb-1`} style={{ fontSize: '1.5rem' }}></i>
                  <span className="small fw-semibold">{item.label}</span>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
