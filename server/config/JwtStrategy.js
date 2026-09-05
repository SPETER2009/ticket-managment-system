const path = require('path');

// Load .env from the server folder
require('dotenv').config({
  path: path.resolve(__dirname, '../.env')
});

console.log("JWT_SECRET =", process.env.JWT_SECRET);

const JwtStrategy = require('passport-jwt').Strategy;
const ExtractJwt = require('passport-jwt').ExtractJwt;
const User = require('../models').User;

// JWT options
const opts = {};

opts.jwtFromRequest = ExtractJwt.fromAuthHeaderAsBearerToken();
opts.secretOrKey = process.env.JWT_SECRET;

// Check if JWT_SECRET exists
if (!opts.secretOrKey) {
  console.error('ERROR: JWT_SECRET is not defined in server/.env');
  process.exit(1);
}

// Initialize JWT strategy
function initialize(passport) {
  const authenticateUser = (jwt_payload, done) => {
    User.findOne({
      where: {
        id: jwt_payload.id
      }
    })
      .then((user) => {
        if (user) {
          return done(null, user);
        } else {
          return done(null, false);
        }
      })
      .catch((err) => {
        return done(err, false);
      });
  };

  passport.use(
    new JwtStrategy(opts, authenticateUser)
  );
}

module.exports = initialize;