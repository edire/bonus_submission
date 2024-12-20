#%% Libraries

import os
from flask import Flask, redirect, request, url_for, session, render_template_string, render_template
from google_auth_oauthlib.flow import Flow
import numpy as np
import requests
from dbharbor.mysql import SQL


#%% Flask Setup

app = Flask(__name__)
app.secret_key = os.urandom(24)
con = SQL()


#%% Google OAuth

CLIENT_SECRETS_FILE = os.getenv('CLIENT_SECRETS_FILE')
SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email"]


def login_required(func):
    def wrapper(*args, **kwargs):
        if not session.get("user_logged_in"):
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


@app.route('/login')
def login():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=url_for('authorize', _external=True, _scheme='https')
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    app.secret_key = state
    return redirect(authorization_url)


@app.route('/authorize')
def authorize():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, 
        scopes=SCOPES, 
        redirect_uri=url_for('authorize', _external=True, _scheme='https')
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    userinfo_response = requests.get(
        'https://www.googleapis.com/oauth2/v2/userinfo',
        headers={'Authorization': f'Bearer {credentials.token}'}
    )
    if userinfo_response.ok:
        userinfo = userinfo_response.json()
        session["user_email"] = userinfo.get("email")
    else:
        raise Exception('Failed to get user email')
    session["user_logged_in"] = True
    return redirect(url_for("home"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))


#%% App

@app.route("/")
def index():
    return "<a href='/login'>Login with Google</a>"


@app.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    df = con.read(f"call analytics.stp_emp_submittal_get('{session['user_email']}')")
    df = df.replace({np.nan: None})
    if request.method == 'POST':
        try:
            bonuses = request.form.getlist('Perc')
            for i, bonus in enumerate(bonuses):
                if bonus != '':
                    bonus = bonus.replace('%', '')
                    bonus = float(bonus)
                    if bonus > 0 and bonus < 1:
                        bonus = bonus * 100
                    sql = f"call analytics.stp_emp_submittal_put('{df.at[i, 'Employee_Code']}', {bonus}, '{session['user_email']}')"
                    con.run(sql)
            df = con.read(f"call analytics.stp_emp_submittal_get('{session['user_email']}')")
            df = df.replace({np.nan: None})
            return render_template('index.html', df=df.to_dict(orient='records'), message="Bonuses updated!")
        except Exception as e:
            return render_template('index.html', df=df.to_dict(orient='records'), message=str(e))
    return render_template('index.html', df=df.to_dict(orient='records'))


@app.route("/test")
def test():
    return str(session.get("user_logged_in"))


@app.route("/email")
@login_required
def email():
    return session["user_email"]


#%%

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)


#%%