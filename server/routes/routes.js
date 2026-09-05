const passport = require('passport');
const userController = require('../controllers/user.controller');
const { getToken, COOKIE_OPTIONS, getRefreshToken, verifyUser } = require('../auth.js');
const jwt = require('jsonwebtoken');

var express = require('express');
var router = express.Router();


router.post('/register', (req, res) => {
  userController.insertUser(req, res);
});

router.post('/login', passport.authenticate('local'), function (req, res) {
  const token = getToken({ id: req.user.id });
  const refreshToken = getRefreshToken({ id: req.user.id });
  res.cookie('refreshToken', refreshToken, COOKIE_OPTIONS);
  res.send({ success: true, token });
});

router.post('/refreshToken', (req, res, next) => {
  const { signedCookies = {} } = req;
  const { refreshToken } = signedCookies;
  if (refreshToken) {
    try {
      const payload = jwt.verify(refreshToken, process.env.REFRESH_TOKEN_SECRET);
      const userId = payload.id;
      const token = getToken({ id: userId });
      const newRefreshToken = getRefreshToken({ id: userId });
      res.cookie('refreshToken', newRefreshToken, COOKIE_OPTIONS);
      res.send({ success: true, token });
    } catch (err) {
      res.statusCode = 401;
      res.send('Unauthorized');
    }
  } else {
    res.statusCode = 401;
    res.send('Unauthorized');
  }
});

router.get('/me', verifyUser, (req, res, next) => {
  res.send(req.user);
});

router.get('/logout', verifyUser, (req, res, next) => {
  res.clearCookie('refreshToken', COOKIE_OPTIONS);
  res.send({ success: true });
});

module.exports = router;
