var express = require('express');
const { verifyUser } = require('../auth.js');
var router = express.Router();
const userController = require('../controllers/user.controller');
const Ticket = require('../models').Ticket;

router.get('/tickets', verifyUser, (req, res) => {
  userController.getTickets(req, res);
});

module.exports = router;
