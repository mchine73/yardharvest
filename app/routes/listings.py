from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import Listing
from app.forms import ListingForm
from app.helpers import geocode_address, save_listing_image, haversine_miles
from app.pricing import get_pricing_config

listings_bp = Blueprint('listings', __name__)


@listings_bp.route('/listings/browse')
def browse():
    page = request.args.get('page', 1, type=int)
    veg_type = request.args.get('type', '')

    q = Listing.query.filter_by(is_active=True).filter(Listing.quantity_available > 0)

    if veg_type:
        q = q.filter_by(vegetable_type=veg_type)

    listings = q.order_by(Listing.created_at.desc()).paginate(page=page, per_page=12, error_out=False)
    return render_template('listings/browse.html', listings=listings, veg_type=veg_type)


@listings_bp.route('/listings/<int:listing_id>')
def detail(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    seller = listing.seller

    user_distance = None
    can_deliver = False
    if current_user.is_authenticated and current_user.latitude and listing.pickup_latitude:
        user_distance = round(haversine_miles(
            current_user.latitude, current_user.longitude,
            listing.pickup_latitude, listing.pickup_longitude
        ), 1)
        if listing.delivery_available and listing.delivery_radius_miles:
            can_deliver = user_distance <= listing.delivery_radius_miles

    return render_template('listings/detail.html', listing=listing, seller=seller,
                           user_distance=user_distance, can_deliver=can_deliver)


@listings_bp.route('/listings/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.can_sell():
        flash('You need a seller account to create listings.', 'warning')
        return redirect(url_for('main.index'))

    form = ListingForm()
    if form.validate_on_submit():
        listing = Listing(
            seller_id=current_user.id,
            title=form.title.data,
            description=form.description.data,
            vegetable_type=form.vegetable_type.data,
            price=form.price.data,
            unit=form.unit.data,
            quantity_available=form.quantity_available.data,
            delivery_available=form.delivery_available.data,
            delivery_radius_miles=form.delivery_radius_miles.data or 0,
            pickup_instructions=form.pickup_instructions.data,
        )

        # Set dynamic pricing fields
        config = get_pricing_config()
        listing.base_price = form.price.data
        listing.initial_quantity = form.quantity_available.data
        listing.price_floor = round(form.price.data * config.floor_pct, 2)
        listing.price_ceiling = round(form.price.data * config.ceiling_pct, 2)
        listing.smart_pricing_enabled = True

        if form.use_profile_address.data:
            listing.pickup_address = current_user.address
            listing.pickup_city = current_user.city
            listing.pickup_state = current_user.state
            listing.pickup_zip = current_user.zip_code
            listing.pickup_latitude = current_user.latitude
            listing.pickup_longitude = current_user.longitude
        else:
            listing.pickup_address = form.pickup_address.data
            listing.pickup_city = form.pickup_city.data
            listing.pickup_state = form.pickup_state.data
            listing.pickup_zip = form.pickup_zip.data
            lat, lon = geocode_address(form.pickup_address.data, form.pickup_city.data,
                                       form.pickup_state.data, form.pickup_zip.data)
            listing.pickup_latitude = lat
            listing.pickup_longitude = lon

        if form.image.data:
            listing.image_filename = save_listing_image(form.image.data)
        if form.image_2.data:
            listing.image_filename_2 = save_listing_image(form.image_2.data)
        if form.image_3.data:
            listing.image_filename_3 = save_listing_image(form.image_3.data)

        db.session.add(listing)
        db.session.commit()
        flash('Listing created!', 'success')
        return redirect(url_for('listings.detail', listing_id=listing.id))

    return render_template('listings/create.html', form=form)


@listings_bp.route('/listings/<int:listing_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if listing.seller_id != current_user.id:
        abort(403)

    form = ListingForm(obj=listing)
    if form.validate_on_submit():
        listing.title = form.title.data
        listing.description = form.description.data
        listing.vegetable_type = form.vegetable_type.data
        listing.price = form.price.data
        # Update pricing fields if price changed
        if form.price.data != listing.base_price:
            config = get_pricing_config()
            listing.base_price = form.price.data
            listing.price_floor = round(form.price.data * config.floor_pct, 2)
            listing.price_ceiling = round(form.price.data * config.ceiling_pct, 2)
        listing.unit = form.unit.data
        listing.quantity_available = form.quantity_available.data
        listing.delivery_available = form.delivery_available.data
        listing.delivery_radius_miles = form.delivery_radius_miles.data or 0
        listing.pickup_instructions = form.pickup_instructions.data

        if form.use_profile_address.data:
            listing.pickup_address = current_user.address
            listing.pickup_city = current_user.city
            listing.pickup_state = current_user.state
            listing.pickup_zip = current_user.zip_code
            listing.pickup_latitude = current_user.latitude
            listing.pickup_longitude = current_user.longitude
        else:
            listing.pickup_address = form.pickup_address.data
            listing.pickup_city = form.pickup_city.data
            listing.pickup_state = form.pickup_state.data
            listing.pickup_zip = form.pickup_zip.data
            lat, lon = geocode_address(form.pickup_address.data, form.pickup_city.data,
                                       form.pickup_state.data, form.pickup_zip.data)
            listing.pickup_latitude = lat
            listing.pickup_longitude = lon

        if form.image.data:
            listing.image_filename = save_listing_image(form.image.data)
        if form.image_2.data:
            listing.image_filename_2 = save_listing_image(form.image_2.data)
        if form.image_3.data:
            listing.image_filename_3 = save_listing_image(form.image_3.data)

        db.session.commit()
        flash('Listing updated!', 'success')
        return redirect(url_for('listings.detail', listing_id=listing.id))

    return render_template('listings/edit.html', form=form, listing=listing)


@listings_bp.route('/listings/<int:listing_id>/toggle', methods=['POST'])
@login_required
def toggle(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if listing.seller_id != current_user.id:
        abort(403)
    listing.is_active = not listing.is_active
    db.session.commit()
    status = 'activated' if listing.is_active else 'deactivated'
    flash(f'Listing {status}.', 'success')
    return redirect(url_for('listings.my_listings'))


@listings_bp.route('/listings/<int:listing_id>/delete', methods=['POST'])
@login_required
def delete(listing_id):
    listing = Listing.query.get_or_404(listing_id)
    if listing.seller_id != current_user.id:
        abort(403)
    listing.is_active = False
    db.session.commit()
    flash('Listing removed.', 'success')
    return redirect(url_for('listings.my_listings'))


@listings_bp.route('/my-listings')
@login_required
def my_listings():
    if not current_user.can_sell():
        flash('You need a seller account.', 'warning')
        return redirect(url_for('main.index'))
    listings = Listing.query.filter_by(seller_id=current_user.id).order_by(Listing.created_at.desc()).all()
    return render_template('listings/my_listings.html', listings=listings)
