'use strict';
const { Model } = require('sequelize');
module.exports = (sequelize, DataTypes) => {
  class Ticket extends Model {
    /**
     * Helper method for defining associations.
     * This method is not a part of Sequelize lifecycle.
     * The `models/index` file will call this method automatically.
     */
    static associate(models) {
      Ticket.belongsTo(models.User, { foreignKey: 'user_id' });
      Ticket.belongsTo(models.Priority, { foreignKey: 'priority_id' });
    }
  }
  Ticket.init(
    {
      user_id: DataTypes.INTEGER,
      priority_id: DataTypes.INTEGER,
      title: DataTypes.STRING,
      description: DataTypes.STRING,
      status: {
        type: DataTypes.STRING,
        defaultValue: 'Open',
      },
    },
    {
      sequelize,
      modelName: 'Ticket',
    }
  );

  return Ticket;
};
