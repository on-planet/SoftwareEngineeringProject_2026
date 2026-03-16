/** li.pengyang-v1.0.0 APP License By  */
 ;'use strict';

/*
 * @Description:
 * @Author: qu.hui@trs.com.cn
 * @Date: 2023-09-11 16:30:59
 */
Vue.component('week-table-component', {
  template: '#week-table-component',
  props: {
    current_date: {
      type: String,
      default: ''
    },
    side_type_select: {
      type: String,
      default: ''
    },
    productionClass: {
      type: String,
      default: 'all'
    }
  },
  watch: {
    current_date: {
      handler: function handler(newVal, oldVal) {
        var _this = this;

        this.type_select = 'all';
        this.form.searchCate = 'all'
        this.form.searchCateItem = '';
        this.recordCateIndex = 'all';
        this.showSelect = false;
        this.$nextTick(function () {
          _this.showSelect = true;
        });
        this.queryTableData_week();
      }
    }
  },
  data: function data() {
    return {
      type_select: 'all',
      showSelect: true,
      loading: false, // 加载状态
      json: {}, // 原始数据
      data_path: '', // 路径
      isshowDouble: false, // 是否显示单双边
      singlenoteObj: {}, // 单双变对应的对象
      isShowReportMemo1: false, // 表格1备注是否显示
      reportMemo1: {}, // 表格1备注
      isShowReportMemo3: false, // 表格3备注是否显示
      reportMemo3: {}, // 表格3备注
      recordName: [], // 记录每个table下的name
      recordList: [], // 记录每个table下的具体内容
      resultList: [], // 最终的结果数组
      isShowMore1: false, // 备注的展开是否更多
      isShowMore3: false, // 备注的展开是否更多
      pro_list1: [], // 第二张表格的数据
      pro_list2: [], // 第三张表格的数据
      table3_date: '', // table3的时间
      noData: false, // 暂无数据
      isShowOtherTable: true, // 是否显示其他表格
      // 新增参数
      isShowMobilePage: false,
      form: {
        searchCate: 'all',
        searchCateItem: ''
      },
      select_doc: {}, // 新增 记录品类信息
      select_arr1: {}, // 新增 记录大类信息
      select_arr2: {}, // 新增 记录小类信息
      recordCateIndex: 'all', // 新增
    };
  },
  mounted: function mounted() {
    // this.queryTableData_week();
    // 新增
    if (screenWidth < 750) {
      this.isShowMobilePage = true;
      this.select_doc = getProductList(enumObj.originalType.shfe, '1');
      this.select_arr1 = this.select_doc.name;
      this.select_arr2 = this.select_doc.list;
    } else {
      this.isShowMobilePage = false;
    }
  },


  methods: {
    // 新增 金属、能源化工、金属
    handleCateTab: function handleCateTab(value) {
      this.recordCateIndex = value;
      if (value !== 'all') {
        this.form.searchCateItem = this.select_arr2[this.recordCateIndex][0].productid;
      } else {
        this.form.searchCateItem = 'all';
      }
      this.resultList = {};
      this.$nextTick(() => {
        this.getProductionId_info(this.form.searchCateItem);
      })
    },
    // 新增 种类： 铜...
    handleCateItemTab: function handleCateItemTab(value) {
      this.resultList = {};
      this.$nextTick(() => {
        this.getProductionId_info(value);
      })
    },

    // 新增 url携带参数，下拉框赋值处理
    handleselectdefault: function handleselectdefault(side_type_select) {
      let recordItemIndexList = [];
      recordItemIndexList = this.findElementWithPropertyIndex(this.select_arr2, 'productid', side_type_select)
      this.form.searchCate = recordItemIndexList[0];
      this.recordCateIndex = recordItemIndexList[0];
      this.$nextTick(() => {
        this.form.searchCateItem = side_type_select;
      });
    },
    // 新增
    findElementWithPropertyIndex: function findElementWithPropertyIndex(arr, propertyName, propertyValue, parentIndex = []) {
      for (let i = 0; i < arr.length; i++) {
        if (Array.isArray(arr[i])) {
          // 如果当前元素是数组，则递归调用
          const result = findElementWithPropertyIndex(arr[i], propertyName, propertyValue, [...parentIndex, i]);
          if (result !== null) {
            return result;
          }
        } else if (typeof arr[i] === 'object' && arr[i] !== null) {
          // 如果当前元素是对象，检查它的属性
          if (arr[i][propertyName] === propertyValue) {
            // 如果找到具有特定属性值的对象，返回当前下标和所属上一层数组的下标
            return [...parentIndex, i];
          }
        }
      }
      return null; // 如果没有找到具有特定属性值的对象，返回null
    },

    // 每周行情数据请求
    queryTableData_week: function queryTableData_week() {
      this.noData = false;
      this.loading = true;
      var vm = this;

      this.type_select = 'all';
      this.showSelect = false;
      this.$nextTick(function () {
        this.showSelect = true;
      });

      if (this.type_select === 'all') {
        this.isShowOtherTable = true;
      } else {
        this.isShowOtherTable = false;
      }
      // 报表数据查询
      $.ajax({
        url: api_future_week(vm.current_date),
        dataType: 'json',
        success: function success(json) {
          vm.loading = false;
          //  没有数据的情况
          if (json.o_cursor.length === 0) {
            vm.noData = true;
            return;
          }
          vm.json = json;
          //console.log(vm.json);
          let pro_options_type =  pro_analysisUrl()
          if (vm.side_type_select && pro_options_type == '1') {
            if (screenWidth > 750) {
              vm.$refs.type_select.getProductionId(vm.side_type_select);
            } else {
              vm.handleselectdefault(vm.side_type_select);
              vm.getProductionId_info(vm.side_type_select);
            }
            return;
          }
          // 针对表格数据进行处理
          vm.handleJsonData();
        },
        error: function error() {
          // 没有数据
          vm.loading = false;
          vm.noData = true;
        }
      });
    },

    // 数据筛选
    getProductionId_info: function getProductionId_info(id) {
      //console.log(id);
      this.type_select = id;
      if (this.type_select === 'all') {
        this.isShowOtherTable = true;
      } else {
        this.isShowOtherTable = false;
      }
      this.$nextTick( () => {
        this.handleJsonData();
      })

    },

    // 是否展开备注
    isExpand: function isExpand(type) {
      var vm = this;
      if (type == '1') {
        vm.isShowMore1 = !vm.isShowMore1;
      } else {
        vm.isShowMore3 = !vm.isShowMore3;
      }
    },

    // table首行特殊样式
    rowClassName: function rowClassName(_ref) {
      var row = _ref.row,
          rowIndex = _ref.rowIndex;

      if (rowIndex === 0) {
        return 'special_row_type';
      }
      if (row.PRODUCTID === enumObj.field_key_all_total || row.INSTRUMENTID.includes(enumObj.field_key_all_total) || row.INSTRUMENTID.includes(enumObj.field_key_subtotal)) {
        return "isTotal";
      }
    },

    // 处理报表数据
    handleJsonData: function handleJsonData() {
      var _this2 = this;

      // 表格处理
      var tableData = JSON.parse(JSON.stringify(this.json));
      //console.log(this.type_select);
      if (this.type_select !== 'all') {
        tableData.o_cursor = this.json.o_cursor.filter(function (item) {
          return item.PRODUCTID.trim() === _this2.type_select;
        });
      }

      // 获取是否显示单双边备注的endeffectivedate
      this.singlenoteObj = getReportSingleDoubleMemo('shfe_week', 'report_issinglenote');
      // 头部单双边备注示例, 动态
      //console.log(this.current_date, this.singlenoteObj.endeffectivedate);
      if (this.current_date < this.singlenoteObj.endeffectivedate) {
        this.isshowDouble = true;
      }
      // 第一张表格的数据
      var pro_list = tableData.o_cursor;
      tableData.o_cursor.forEach( item => {
        if( item.PRODUCTID && item.PRODUCTID.includes('efp') ) {
          item.PRODUCTID = item.PRODUCTID.split('efp')[0] + '_f';
        }
      } )
      //console.log(tableData);
      // 将数组分为多产品数组
      var only_info = listParamsRepeat(tableData.o_cursor, 'PRODUCTID');
      // 针对数组进行的保留小数点位数precision---字段的添加
      pro_precision(only_info, 'decimal_number');
      this.recordName = [];
      this.recordList = [];
      // 针对的是上海期货交易所期货合约行情的表格处理
      only_info.forEach(function (item) {
        var arrItem = {
          PRODUCTNAME: getProductProp(item.PRODUCTID, 'productname'),
          PRODUCTID: item.PRODUCTID,
          TYPE_LINE: true, // 首行商品名称的标识
          tas_start_date: ''
        };
        var tas_item = getProductProp(item.PRODUCTID.trim(), enumObj.tas_start_date);
        if (tas_item) {
          arrItem.tas_start_date = tas_item;
        }

        if (item.PRODUCTID.includes(enumObj.field_key_tas)) {
          // 获取每一项里面的tas_start_date属性
          var str = getProductProp(item.PRODUCTID.trim(), enumObj.tas_start_date);
          arrItem.tas_start_date = str;
        }
        _this2.recordName.push(arrItem);

        var recordListItem = [];
        pro_list.forEach(function (m) {
          if (m.PRODUCTID.trim() === item.PRODUCTID.trim()) {
            m.precision = item.precision;
            recordListItem.push(m);
          }
        });
        _this2.recordList.push(recordListItem);
      });
      var recordlistInfo = JSON.parse(JSON.stringify(this.recordList));
      this.recordList.forEach(function (item, index) {
        if (item.length == 1 && item.some(function (item) {
          return item.INSTRUMENTID === enumObj.field_key_all_total;
        })) {
          recordlistInfo[index - 1].push(recordlistInfo[index][0]);
          recordlistInfo.splice(index, 1);
        }
      });
      this.resultList = []; 
//    this.resultList = recordlistInfo;

      // 针对总计进行特殊处理
      this.recordName.forEach(function (item, index) {
        if (item.INSTRUMENTID === enumObj.field_key_all_total) {
          _this2.recordName.splice(index, 1);
        }
      });

           
      this.$nextTick( () => {
        this.resultList = recordlistInfo;
        // 针对首行商品名称做处理
        this.resultList.forEach(function (item, index) {
          item.unshift({
            INSTRUMENTID: _this2.isShowMobilePage ? (_this2.recordName[index].PRODUCTNAME) : ('商品名称:' + _this2.recordName[index].PRODUCTNAME)

          });
        });

//      
        this.reportMemo1 = getReportMemo('shfe_week', enumObj.report_1_note_total, this.current_date);
        this.$nextTick(function () {
            _this2.$refs.report_memo1 && _this2.$refs.report_memo1.handleBtn(_this2.reportMemo1);
        });
      })

      // 第三张表格的数据
      this.pro_list2 = tableData.o_curmetalindex;

//    获取备注
//    this.reportMemo1 = getReportMemo('shfe_week', enumObj.report_1_note_total, this.current_date);
      this.reportMemo3 = getReportMemo('shfe_week', enumObj.report_2_note_total, this.current_date);
//    传递备注信息到公共备注组件中去
//    this.$nextTick(function () {
//         _this2.$refs.report_memo1 && _this2.$refs.report_memo1.handleBtn(_this2.reportMemo1);
//    });
      if (this.type_select === 'all') {
        this.$nextTick(function () {
          _this2.$refs.report_memo3.handleBtn(_this2.reportMemo3);
        });
      }
    },


    // 整个页面打印
    printTable: function (_printTable) {
      function printTable() {
        return _printTable.apply(this, arguments);
      }

      printTable.toString = function () {
        return _printTable.toString();
      };

      return printTable;
    }(function () {
      // 全局方法-打印
      printTable();
    }),


    // 导出excell和txt
    exportExcel: function (_exportExcel) {
      function exportExcel(_x, _x2) {
        return _exportExcel.apply(this, arguments);
      }

      exportExcel.toString = function () {
        return _exportExcel.toString();
      };

      return exportExcel;
    }(function (name, type) {
      // 全局方法-导出excell和txt
      exportExcel(name, type);
    })
  }
});