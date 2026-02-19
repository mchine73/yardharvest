from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (StringField, PasswordField, TextAreaField, FloatField,
                     IntegerField, SelectField, BooleanField, SubmitField, HiddenField)
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, Optional, ValidationError
from app.models import User
from app.helpers import VEGETABLE_CATEGORIES, UNIT_CHOICES


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(3, 80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(6, 128)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('I want to', choices=[
        ('buyer', 'Buy produce'),
        ('seller', 'Sell produce'),
        ('both', 'Buy and Sell')
    ])
    address = StringField('Street Address', validators=[Optional()])
    city = StringField('City', validators=[DataRequired()])
    state = StringField('State', validators=[DataRequired()])
    zip_code = StringField('ZIP Code', validators=[DataRequired(), Length(5, 10)])
    submit = SubmitField('Create Account')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Username already taken.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')


class ListingForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(3, 150)])
    description = TextAreaField('Description', validators=[DataRequired()])
    vegetable_type = SelectField('Category', choices=VEGETABLE_CATEGORIES)
    price = FloatField('Price ($)', validators=[DataRequired(), NumberRange(min=0.01)])
    unit = SelectField('Unit', choices=UNIT_CHOICES)
    quantity_available = IntegerField('Quantity Available', validators=[DataRequired(), NumberRange(min=1)])
    image = FileField('Photo', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'])])
    image_2 = FileField('Photo 2 (optional)', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'])])
    image_3 = FileField('Photo 3 (optional)', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'])])
    use_profile_address = BooleanField('Use my profile address for pickup', default=True)
    pickup_address = StringField('Pickup Address', validators=[Optional()])
    pickup_city = StringField('City', validators=[Optional()])
    pickup_state = StringField('State', validators=[Optional()])
    pickup_zip = StringField('ZIP', validators=[Optional()])
    delivery_available = BooleanField('I can deliver')
    delivery_radius_miles = FloatField('Delivery radius (miles)', validators=[Optional(), NumberRange(min=0.5, max=50)])
    pickup_instructions = TextAreaField('Pickup Instructions', validators=[Optional()])
    submit = SubmitField('Save Listing')


class SearchForm(FlaskForm):
    class Meta:
        csrf = False  # GET form, no CSRF needed

    keyword = StringField('Search', validators=[Optional()])
    vegetable_type = SelectField('Category', choices=[('', 'All Categories')] + VEGETABLE_CATEGORIES)
    location = StringField('Near (ZIP or city)', validators=[Optional()])
    radius = SelectField('Within', choices=[
        ('5', '5 miles'), ('10', '10 miles'), ('25', '25 miles'), ('50', '50 miles')
    ], default='10')
    max_price = FloatField('Max Price', validators=[Optional()])
    delivery_only = BooleanField('Delivery available')
    submit = SubmitField('Search')


class MessageForm(FlaskForm):
    body = TextAreaField('Message', validators=[DataRequired(), Length(1, 2000)])
    recipient_id = HiddenField(validators=[DataRequired()])
    listing_id = HiddenField(validators=[Optional()])
    submit = SubmitField('Send')


class ReviewForm(FlaskForm):
    rating = SelectField('Rating', choices=[
        ('5', '5 - Excellent'),
        ('4', '4 - Great'),
        ('3', '3 - Good'),
        ('2', '2 - Fair'),
        ('1', '1 - Poor')
    ], coerce=int)
    comment = TextAreaField('Review', validators=[DataRequired(), Length(10, 1000)])
    submit = SubmitField('Submit Review')


class ProfileForm(FlaskForm):
    display_name = StringField('Display Name', validators=[Optional(), Length(max=100)])
    bio = TextAreaField('About Your Garden', validators=[Optional()])
    address = StringField('Street Address', validators=[Optional()])
    city = StringField('City', validators=[DataRequired()])
    state = StringField('State', validators=[DataRequired()])
    zip_code = StringField('ZIP Code', validators=[DataRequired(), Length(5, 10)])
    profile_image = FileField('Profile Photo', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'])])
    gardening_story = TextAreaField('My Gardening Story', validators=[Optional(), Length(max=2000)])
    years_gardening = IntegerField('Years Gardening', validators=[Optional(), NumberRange(min=0, max=100)])
    gallery_image_1 = FileField('Garden Photo 1', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'])])
    gallery_image_2 = FileField('Garden Photo 2', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'])])
    gallery_image_3 = FileField('Garden Photo 3', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'])])
    submit = SubmitField('Save Profile')
