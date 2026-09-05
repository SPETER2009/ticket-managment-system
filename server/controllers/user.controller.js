const User = require('../models').User;
const Ticket = require('../models').Ticket;
const Priority = require('../models').Priority;
const { getToken, getRefreshToken, COOKIE_OPTIONS } = require('../auth');

//create and save user
exports.insertUser = (req, res) => {
  if (!req.body.username || !req.body.password || !req.body.email) {
    res.status(400).send({
      message: 'Content can not be empty!',
    });
    return;
  }
  const user = {
    username: req.body.username,
    password: req.body.password,
    email: req.body.email,
  };

  User.create(user)
    .then((createdUser) => {
      const token = getToken({ id: createdUser.id });
      const refreshToken = getRefreshToken({ id: createdUser.id });
      res.cookie('refreshToken', refreshToken, COOKIE_OPTIONS);
      res.send({ success: true, token });
    })
    .catch((err) => {
      if (err.errors && err.errors.length > 0) {
        if (err.errors[0].path === 'username') {
          return res.status(409).send({
            code: 'auth-01',
            message: 'Username already registered',
          });
        }

        if (err.errors[0].path === 'email') {
          return res.status(409).send({
            code: 'auth-02',
            message: 'Email already registered',
          });
        }
      }
      
      return res.status(500).send({
        message: err.message || 'Some error occurred while creating the User.',
      });
    });
};

exports.getTickets = (req, res) => {
  const id = req.user.id;
  Ticket.findAll({
    include: [
      {
        model: User,
        required: true,
        where: { id: id },
        attributes: [],
      },
      {
        model: Priority,
        required: true,
        attributes: ['priority', 'id'],
      },
    ],
    attributes: ['id', 'title', 'description', 'status'],
  })
    .then(async (response) => {
      res.send(response);
    })
    .catch((err) => console.log(err));
};
