const bcrypt = require('bcrypt');
('use strict');
const { Model } = require('sequelize');

module.exports = (sequelize, DataTypes) => {
  class User extends Model {
    /**
     * Helper method for defining associations.
     * This method is not a part of Sequelize lifecycle.
     * The `models/index` file will call this method automatically.
     */
    static associate(models) {
      User.hasMany(models.Ticket, { foreignKey: 'user_id' });
    }
  }
  User.init(
    {
      username: DataTypes.STRING,
      password: DataTypes.STRING,
      email: DataTypes.STRING,
    },
    {
      sequelize,
      modelName: 'User',
    }
  );

  User.addHook('beforeBulkCreate', async (users, option) => {
    for (const user of users) {
      const salt = await bcrypt.genSaltSync(10, 'a');
      user.password = bcrypt.hashSync(user.password, salt);
      user.createdAt = new Date();
      user.updatedAt = new Date();
    }
  });
  User.addHook('beforeCreate', async (user, options) => {
    const salt = await bcrypt.genSaltSync(10, 'a');
    user.password = bcrypt.hashSync(user.password, salt);
    user.createdAt = new Date();
    user.updatedAt = new Date();
  });

  User.verifyPassword = (password, hashpassword) => {
    return bcrypt.compareSync(password, hashpassword);
  };

  return User;
};
