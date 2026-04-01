(function(){
  var hasBooted=false;

  function closeOpenPortalMenus(){
    document.querySelectorAll('.portal-shell-menu[open], [data-portal-mobile-nav] .site-shell-mobile[open]').forEach(function(menu){
      menu.removeAttribute('open');
    });
  }

  function bindPortalMenus(){
    document.querySelectorAll('.portal-shell-menu__backdrop').forEach(function(backdrop){
      backdrop.addEventListener('click',function(){
        closeOpenPortalMenus();
      });
    });

    document.addEventListener('click',function(event){
      document.querySelectorAll('.portal-shell-menu[open], [data-portal-mobile-nav] .site-shell-mobile[open]').forEach(function(menu){
        if(menu.contains(event.target)){return;}
        menu.removeAttribute('open');
      });
    });

    document.addEventListener('keydown',function(event){
      if(event.key==='Escape'){
        closeOpenPortalMenus();
      }
    });

    document.querySelectorAll('.portal-shell-menu__panel a, [data-portal-mobile-nav] .site-shell-mobile-panel a').forEach(function(link){
      link.addEventListener('click',function(){
        closeOpenPortalMenus();
      });
    });
  }

  function csrf(){
    var match=document.cookie.match(/(?:^|; )csrf_token=([^;]+)/);
    if(match){return decodeURIComponent(match[1]);}
    if(window.frappe&&frappe.csrf_token){return frappe.csrf_token;}
    if(window.csrf_token){return window.csrf_token;}
    return '';
  }

  function extractMessage(body){
    if(body&&body.message){body=body.message;}
    if(body&&body._server_messages){
      try{
        var messages=JSON.parse(body._server_messages);
        if(messages&&messages.length){return JSON.parse(messages[0]).message||'Unable to save changes.';}
      }catch(_error){}
    }
    if(body&&body.exc){return 'Unable to save changes.';}
    if(typeof body==='string'&&body){return body;}
    if(body&&body.message){return body.message;}
    return '';
  }

  function unwrapPayload(body){
    if(body&&body.message){return body.message;}
    return body||{};
  }

  function setMessage(messageBox,text,isError){
    if(!messageBox){return;}
    messageBox.textContent=text||'';
    messageBox.classList.remove('is-visible','is-error');
    if(text){
      messageBox.classList.add('is-visible');
      if(isError){messageBox.classList.add('is-error');}
    }
  }

  function setFormBusy(form,busy){
    var shouldDisable=!!busy;
    form.dataset.portalSubmitting=shouldDisable?'1':'0';
    form.querySelectorAll('input, select, textarea, button').forEach(function(control){
      if(control&&control.type==='hidden'){return;}
      control.disabled=shouldDisable;
    });
  }

  async function submitPayload(form,payload){
    var endpoint=form.getAttribute('data-portal-endpoint');
    if(!endpoint||form.dataset.portalSubmitting==='1'){return;}
    closeOpenPortalMenus();
    var messageBox=form.querySelector('[data-portal-message]');
    setMessage(messageBox,'',false);

    try{
      setFormBusy(form,true);
      var response=await fetch(endpoint,{
        method:'POST',
        credentials:'same-origin',
        headers:{
          'Content-Type':'application/json',
          'X-Frappe-CSRF-Token':csrf()
        },
        body:JSON.stringify(payload)
      });
      var body=await response.json().catch(function(){return {};});
      if(!response.ok||body.exc||body.exception){
        throw new Error(extractMessage(body)||'Unable to save changes.');
      }
      setMessage(messageBox,extractMessage(body)||'Changes saved.',false);
      setFormBusy(form,false);
      return unwrapPayload(body);
    }catch(error){
      setFormBusy(form,false);
      if(messageBox){
        setMessage(messageBox,error.message||'Unable to save changes.',true);
      }else{
        window.alert(error.message||'Unable to save changes.');
      }
      throw error;
    }
  }

  function serializeStandardForm(form){
    var formData=new FormData(form);
    var payload={};
    formData.forEach(function(value,key){payload[key]=value;});
    return payload;
  }

  function refreshChecklistEmptyState(form){
    var emptyState=form.querySelector('[data-checklist-empty]');
    var list=form.querySelector('[data-portal-checklist-list]');
    if(!emptyState||!list){return;}
    var hasItems=!!list.querySelector('[data-checklist-item]');
    emptyState.hidden=hasItems;
  }

  function fillChecklistRow(row,item){
    row.querySelectorAll('[data-checklist-field]').forEach(function(field){
      var key=field.getAttribute('data-checklist-field');
      if(field.type==='checkbox'){
        field.checked=!!(item&&item[key]);
        return;
      }
      field.value=item&&item[key] ? item[key] : '';
    });
  }

  function appendChecklistRow(form,item){
    var list=form.querySelector('[data-portal-checklist-list]');
    var template=form.querySelector('template[data-checklist-template]');
    if(!list||!template){return null;}
    var fragment=template.content.cloneNode(true);
    var row=fragment.querySelector('[data-checklist-item]');
    fillChecklistRow(row,item||{});
    list.appendChild(fragment);
    refreshChecklistEmptyState(form);
    return list.lastElementChild;
  }

  function renderChecklistRows(form,items){
    var list=form.querySelector('[data-portal-checklist-list]');
    if(!list){return;}
    list.innerHTML='';
    (items||[]).forEach(function(item){
      appendChecklistRow(form,item);
    });
    refreshChecklistEmptyState(form);
  }

  function moveChecklistRow(row,direction){
    if(!row||!row.parentElement){return;}
    if(direction==='up'&&row.previousElementSibling){
      row.parentElement.insertBefore(row,row.previousElementSibling);
    }
    if(direction==='down'&&row.nextElementSibling){
      row.parentElement.insertBefore(row.nextElementSibling,row);
    }
  }

  function serializeChecklistForm(form){
    var buildingField=form.querySelector('[data-checklist-field="building_name"]');
    var payload={building_name:buildingField?buildingField.value:'' , items:[]};
    form.querySelectorAll('[data-checklist-item]').forEach(function(row){
      var item={};
      row.querySelectorAll('[data-checklist-field]').forEach(function(field){
        var key=field.getAttribute('data-checklist-field');
        item[key]=field.type==='checkbox' ? field.checked : (field.value||'').trim();
      });
      var isBlank=!item.title&&!item.description&&!item.requires_photo_proof;
      if(isBlank){return;}
      if(!item.title){
        throw new Error('Each checklist item needs a title.');
      }
      payload.items.push({
        item_id:item.item_id||'',
        title:item.title,
        description:item.description||'',
        requires_photo_proof:!!item.requires_photo_proof
      });
    });
    return payload;
  }

  function applyChecklistResponse(form,payload){
    if(payload&&Array.isArray(payload.selected_building_checklist)){
      renderChecklistRows(form,payload.selected_building_checklist);
    }
    var versionMeta=form.closest('.portal-card').querySelector('[data-checklist-version-meta]');
    if(versionMeta&&payload&&payload.selected_building_sop){
      var version=payload.selected_building_sop;
      var parts=['Version '+(version.version_number||0)];
      if(version.updated_label){parts.push('Updated '+version.updated_label);}
      if(typeof version.item_count!=='undefined'){
        parts.push((version.item_count||0)+' items');
      }
      versionMeta.innerHTML=parts.map(function(text){return '<span>'+text+'</span>';}).join('');
      versionMeta.hidden=false;
    }
  }

  async function submitForm(form){
    await submitPayload(form,serializeStandardForm(form));
  }

  async function submitChecklistForm(form){
    var payload=serializeChecklistForm(form);
    var responsePayload=await submitPayload(form,payload);
    applyChecklistResponse(form,responsePayload||{});
  }

  function boot(){
    if(hasBooted){return;}
    hasBooted=true;
    bindPortalMenus();
    document.querySelectorAll('form[data-portal-endpoint]:not([data-portal-checklist-form])').forEach(function(form){
      form.addEventListener('submit',function(event){
        event.preventDefault();
        submitForm(form);
      });
    });
    document.querySelectorAll('form[data-portal-checklist-form]').forEach(function(form){
      refreshChecklistEmptyState(form);
      form.addEventListener('click',function(event){
        var button=event.target.closest('[data-checklist-add],[data-checklist-remove],[data-checklist-move]');
        if(!button){return;}
        event.preventDefault();
        if(button.hasAttribute('data-checklist-add')){
          appendChecklistRow(form,{});
          return;
        }
        var row=button.closest('[data-checklist-item]');
        if(button.hasAttribute('data-checklist-remove')&&row){
          row.remove();
          refreshChecklistEmptyState(form);
          return;
        }
        var direction=button.getAttribute('data-checklist-move');
        if(row&&direction){moveChecklistRow(row,direction);}
      });
      form.addEventListener('submit',function(event){
        event.preventDefault();
        submitChecklistForm(form).catch(function(){});
      });
    });
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',boot,{once:true});
  }else{
    boot();
  }
})();
