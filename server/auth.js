const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '.env') });
const passport = require('passport');
const jwt = require('jsonwebtoken');

const isProduction = process.env.NODE_ENV === 'production';

exports.COOKIE_OPTIONS = {
  httpOnly: true,
  secure: isProduction,
  signed: true,
  maxAge: eval(process.env.REFRESH_TOKEN_EXPIRY || '60 * 60 * 24 * 30') * 1000,
  sameSite: isProduction ? 'none' : 'lax',
};

exports.getToken = (user) => {
  return jwt.sign(user, process.env.JWT_SECRET, {
    expiresIn: eval(process.env.SESSION_EXPIRY || '60 * 15'),
  });
};

exports.getRefreshToken = (user) => {
  return jwt.sign(user, process.env.REFRESH_TOKEN_SECRET, {
    expiresIn: eval(process.env.REFRESH_TOKEN_EXPIRY || '60 * 60 * 24 * 30'),
  });
};

exports.verifyUser = passport.authenticate('jwt', { session: false });
