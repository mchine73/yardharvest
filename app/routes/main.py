from flask import Blueprint, render_template, request
from app.models import Listing
from app.forms import SearchForm
from app.helpers import geocode_address, get_nearby_listings

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    featured = Listing.query.filter_by(is_active=True).filter(
        Listing.quantity_available > 0
    ).order_by(Listing.created_at.desc()).limit(8).all()
    return render_template('index.html', listings=featured)


@main_bp.route('/search')
def search():
    form = SearchForm(request.args)
    listings = []
    searched = False
    user_lat = None
    user_lon = None

    if any([form.keyword.data, form.vegetable_type.data, form.location.data]):
        searched = True
        q = Listing.query.filter_by(is_active=True).filter(Listing.quantity_available > 0)

        if form.keyword.data:
            kw = f'%{form.keyword.data}%'
            q = q.filter(
                (Listing.title.ilike(kw)) |
                (Listing.description.ilike(kw))
            )

        if form.vegetable_type.data:
            q = q.filter_by(vegetable_type=form.vegetable_type.data)

        if form.max_price.data:
            q = q.filter(Listing.price <= form.max_price.data)

        if form.delivery_only.data:
            q = q.filter_by(delivery_available=True)

        if form.location.data:
            lat, lon = geocode_address(None, form.location.data, '', '')
            if lat and lon:
                user_lat, user_lon = lat, lon
                radius = float(form.radius.data or 10)
                listings = get_nearby_listings(lat, lon, radius)
                if form.keyword.data or form.vegetable_type.data or form.max_price.data or form.delivery_only.data:
                    ids = {l.id for l in q.all()}
                    listings = [l for l in listings if l.id in ids]
            else:
                listings = q.order_by(Listing.created_at.desc()).all()
        else:
            listings = q.order_by(Listing.created_at.desc()).all()

    return render_template('search.html', form=form, listings=listings,
                           searched=searched, user_lat=user_lat, user_lon=user_lon)


@main_bp.route('/about')
def about():
    return render_template('about.html')
