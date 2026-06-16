from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import User, Listing, Order, Review
from app.forms import ProfileForm, ReviewForm
from app.helpers import geocode_address, save_listing_image

profile_bp = Blueprint('profile', __name__)


@profile_bp.route('/profile/<int:user_id>')
def public_profile(user_id):
    user = db.get_or_404(User, user_id)
    listings = Listing.query.filter_by(seller_id=user_id, is_active=True).order_by(
        Listing.created_at.desc()).all()
    reviews = Review.query.filter_by(seller_id=user_id).order_by(Review.created_at.desc()).all()
    return render_template('profile/public_profile.html', user=user, listings=listings, reviews=reviews)


@profile_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.display_name = form.display_name.data
        current_user.bio = form.bio.data
        current_user.gardening_story = form.gardening_story.data
        current_user.years_gardening = form.years_gardening.data

        if form.gallery_image_1.data:
            current_user.gallery_image_1 = save_listing_image(form.gallery_image_1.data)
        if form.gallery_image_2.data:
            current_user.gallery_image_2 = save_listing_image(form.gallery_image_2.data)
        if form.gallery_image_3.data:
            current_user.gallery_image_3 = save_listing_image(form.gallery_image_3.data)

        current_user.address = form.address.data
        current_user.city = form.city.data
        current_user.state = form.state.data
        current_user.zip_code = form.zip_code.data

        lat, lon = geocode_address(form.address.data, form.city.data,
                                   form.state.data, form.zip_code.data)
        current_user.latitude = lat
        current_user.longitude = lon

        if form.profile_image.data:
            current_user.profile_image = save_listing_image(form.profile_image.data)

        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile.public_profile', user_id=current_user.id))

    return render_template('profile/edit_profile.html', form=form)


@profile_bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.can_sell():
        flash('Seller account required.', 'warning')
        return redirect(url_for('main.index'))

    active_listings = Listing.query.filter_by(seller_id=current_user.id, is_active=True).count()
    pending_orders = Order.query.filter_by(seller_id=current_user.id, status='pending').count()
    completed_orders = Order.query.filter_by(seller_id=current_user.id, status='completed').count()
    recent_orders = Order.query.filter_by(seller_id=current_user.id).order_by(
        Order.created_at.desc()).limit(5).all()

    return render_template('profile/dashboard.html',
                           active_listings=active_listings,
                           pending_orders=pending_orders,
                           completed_orders=completed_orders,
                           recent_orders=recent_orders)


@profile_bp.route('/orders/<int:order_id>/review', methods=['GET', 'POST'])
@login_required
def leave_review(order_id):
    order = db.get_or_404(Order, order_id)
    if order.buyer_id != current_user.id:
        flash('Not authorized.', 'danger')
        return redirect(url_for('main.index'))
    if order.status != 'completed':
        flash('You can only review completed orders.', 'warning')
        return redirect(url_for('cart.my_orders'))
    if order.review:
        flash('You already reviewed this order.', 'info')
        return redirect(url_for('cart.my_orders'))

    form = ReviewForm()
    if form.validate_on_submit():
        review = Review(
            reviewer_id=current_user.id,
            seller_id=order.seller_id,
            order_id=order.id,
            rating=form.rating.data,
            comment=form.comment.data,
        )
        db.session.add(review)
        db.session.commit()
        flash('Review submitted!', 'success')
        return redirect(url_for('cart.my_orders'))

    return render_template('profile/leave_review.html', form=form, order=order)
