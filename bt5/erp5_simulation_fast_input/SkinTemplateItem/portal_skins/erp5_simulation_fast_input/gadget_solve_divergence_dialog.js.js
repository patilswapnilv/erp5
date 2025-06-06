/*global window, document, rJS, RSVP, Handlebars, jIO, location, console */
/*jslint nomen: true, maxlen:80, indent:2*/
// We should not use "document" since a gadget should be embedded and
// must not deals with other parts. Though here we use this gadget to
// modify an existing dialog, we do not have nice structure of a full
// renderjs web page

(function (rJS, jIO, Handlebars, RSVP, document, window, loopEventListener) {
  "use strict";
  rJS(window)
    .ready(function (g) {
      g.props = {};
    })
    .ready(function (g) {
      return g.getElement().push(function (element) {
        g.props.element = element;
        g.props.filling_count = 0;
      });
    })
    .declareService(function () {
      var gadget = this;
      return loopEventListener(
          document.querySelector('form.main_form'),
          'submit',
          false,
          function (evt) {
            if (gadget.props.filling_count == 0){
              document.querySelector('#dialog_submit_button').click();
            }
          }
        );
    })
    .declareService(function () {
      var gadget = this;
      console.log("location",location);
      // WARNING: This considers that the view (in this case,
      // 'Delivery_solveDivergenceAction') is at the end of the pathname
      // but if there are several pages in the ListBox (not handled), this
      // will not be the case...
      var basedir = location.pathname.split('/').slice(0, -1).join('/') + '/',
        divergence_choice_list = [],
        i,
        divergence_element_choice,
        divergence_element_choice_list = document.querySelectorAll(
          'input[type="radio"]'),
        listener_list = [];

      function fillDialog(event) {
        console.log("fillDialog, event", event);
        console.log("fillDialog, value", event.target.value);
        var solver_decision_uid = event.target.name.split("_").pop();

        var data_cell;
        data_cell = document.evaluate(
          "ancestor::tr[1]//td[@class='listbox-table-data-cell'][3]",
          event.target,
          null,
          XPathResult.FIRST_ORDERED_NODE_TYPE,
          null
        ).singleNodeValue;
        // The purpose here is to not make visible the submit button until
        // there is no error which should not be counted twice...
        if (!data_cell.innerHTML.includes('ERROR')) {
          gadget.props.filling_count += 1;
          var button = document.querySelector('#dialog_submit_button');
          button.disabled = true;
          button.setAttribute('style', 'visibility:hidden');
        }

        return new RSVP.Queue()
          .push(function () {
            return jIO.util.ajax(
              {
                "type": "POST",
                "url":  basedir + 'Delivery_getSolveDivergenceDialogParameterFormBox?solver=' + event.target.value + "&solver_decision_uid=" + solver_decision_uid + "&render_by_gadget=1",
                "xhrFields": {
                  withCredentials: true
                }
              }
            );
          })
          .push(function (data) {
            data_cell.innerHTML = data.target.response;
            gadget.props.filling_count -= 1;
            if (gadget.props.filling_count === 0) {
              var button = document.querySelector('#dialog_submit_button');
              button.disabled = false;
              button.setAttribute('style', 'visibility:visible');
            }
          }, function (error) {
            var error_message;
            if (error.target !== undefined) {
              error_message = '<a class="error" href="' + error.target.responseURL + '">Request failed</a>' +
                ' (' + error.target.status + ' ' + error.target.statusText + ')';
            }
            else {
              error_message = 'Request failed';
            }
            data_cell.innerHTML = '<span class="error"><b>ERROR: ' + error_message + '</b></span>';
          });
      }

      console.log("divergence_element_choice_list", divergence_element_choice_list);
      for (i = 0; i < divergence_element_choice_list.length; i++) {
        divergence_element_choice = divergence_element_choice_list[i];
        console.log("divergence_element_choice.name", divergence_element_choice.name);
        if (divergence_element_choice.name.startsWith("field_listbox_solver_") === true) {
          //divergence_choice_list.push(divergence_element_choice);
          divergence_choice_list.push(loopEventListener(
            divergence_element_choice,
            'change',
            false,
            fillDialog
          ));
        }
      }
      return divergence_choice_list;
    });
}(rJS, jIO, Handlebars, RSVP, document, window, rJS.loopEventListener));