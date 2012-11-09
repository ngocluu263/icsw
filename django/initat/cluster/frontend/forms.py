# -*- coding: utf-8 -*-

""" simple formulars for django / clustersoftware """

from django.forms.widgets import TextInput, PasswordInput
from django.forms import Form, ValidationError, CharField
from django.contrib.auth import authenticate
from django.utils.translation import ugettext_lazy as _

class authentication_form(Form):
    username = CharField(label=_("Username"),
                         max_length=30,
                         widget=TextInput(attrs={"class" : "logininput"}))
    password = CharField(label=_("Password"),
                         widget=PasswordInput(attrs={"class" : "logininput"}))
    def __init__(self, request=None, *args, **kwargs):
        """
        If request is passed in, the form will validate that cookies are
        enabled. Note that the request (a HttpRequest object) must have set a
        cookie with the key TEST_COOKIE_NAME and value TEST_COOKIE_VALUE before
        running this validation.
        """
        self.request = request
        self.user_cache = None
        super(authentication_form, self).__init__(*args, **kwargs)
    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username and password:
            self.user_cache = authenticate(username=username, password=password)
            if self.user_cache is None:
                raise ValidationError(_("Please enter a correct username and password. Note that both fields are case-sensitive."))
            elif not self.user_cache.is_active:
                raise ValidationError(_("This account is inactive."))
        else:
            raise ValidationError(_("Need username and password"))
        # TODO: determine whether this should move to its own method.
        if self.request:
            if not self.request.session.test_cookie_worked():
                raise ValidationError(_("Your Web browser doesn't appear to have cookies enabled. Cookies are required for logging in."))
        return self.cleaned_data
    def get_user(self):
        return self.user_cache
