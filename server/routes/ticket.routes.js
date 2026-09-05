var express = require('express');
const { verifyUser } = require('../auth.js');
var router = express.Router();
const ticketController = require('../controllers/ticketcontroller');

router.post('/', verifyUser, (req, res, next) => {
  ticketController.createTicket(req, res);
});

router.put('/', verifyUser, (req, res, next) => {
  ticketController.updateTicket(req, res);
});

router.post('/delete', verifyUser, (req, res, next) => {
  ticketController.deleteTicket(req, res);
});

module.exports = router;
