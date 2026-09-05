const express = require('express');
var bodyParser = require('body-parser');
const path = require('path');
const db = require('./models');
const passport = require('passport');
const cookieParser = require('cookie-parser');
const cors = require('cors');

require('dotenv').config();

const PORT = process.env.PORT || 3001;

const app = express();
var routes = require('./routes/routes');
var userRoutes = require('./routes/user.routes');
var ticketRoutes = require('./routes/ticket.routes');

db.sequelize.sync({ alter: true });

require('./config/passport-config')(passport);
require('./config/JwtStrategy')(passport);
require('./auth');

app.use(cookieParser(process.env.COOKIE_SECRET));
app.use(bodyParser.json());
app.use(express.static(path.resolve(__dirname, '../client/build')));
app.use(bodyParser.urlencoded({ extended: true }));

const corsOptions = {
  origin: true,
  credentials: true,
};
app.use(passport.initialize());

app.use(cors(corsOptions));

app.use('/', routes);
app.use('/user', userRoutes);
app.use('/ticket', ticketRoutes);

app.get('*', (req, res) => {
  res.sendFile(path.resolve(__dirname, '../client/build/index.html'));
});

app.listen(PORT, () => {
  console.log(`Server listening on port: ${PORT}`);
});
